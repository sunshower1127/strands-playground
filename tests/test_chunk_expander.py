"""ChunkExpander 테스트"""

from unittest.mock import MagicMock

import pytest
from src.rag.chunk_expander import (
    ChunkExpander,
    NeighborChunkExpander,
    NoopChunkExpander,
)


# 테스트용 검색 결과 fixture
@pytest.fixture
def sample_results() -> list[dict]:
    """Rerank 후 Top-K 검색 결과"""
    return [
        {
            "_id": "chunk_1_5",
            "_score": 0.95,
            "_source": {
                "document_id": 1,
                "chunk_index": 5,
                "content": "연차는 15일입니다.",
                "file_name": "휴가정책.md",
            },
        },
        {
            "_id": "chunk_2_10",
            "_score": 0.85,
            "_source": {
                "document_id": 2,
                "chunk_index": 10,
                "content": "병가는 별도 신청이 필요합니다.",
                "file_name": "병가안내.md",
            },
        },
    ]


@pytest.fixture
def mock_opensearch_client():
    """OpenSearch 클라이언트 Mock"""
    client = MagicMock()
    return client


class TestNoopChunkExpander:
    """NoopChunkExpander 테스트 - 확장 안 함"""

    def test_returns_all_results(self, sample_results):
        expander = NoopChunkExpander()

        result = expander.expand(sample_results)

        assert result == sample_results
        assert len(result) == 2

    def test_empty_results(self):
        expander = NoopChunkExpander()

        result = expander.expand([])

        assert result == []

    def test_implements_protocol(self):
        expander = NoopChunkExpander()
        assert isinstance(expander, ChunkExpander)


class TestNeighborChunkExpander:
    """NeighborChunkExpander 테스트 - 이웃 청크 확장"""

    def test_implements_protocol(self, mock_opensearch_client):
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index")
        assert isinstance(expander, ChunkExpander)

    def test_empty_results(self, mock_opensearch_client):
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index")

        result = expander.expand([])

        assert result == []
        mock_opensearch_client.search.assert_not_called()

    def test_default_window_is_5(self, mock_opensearch_client):
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index")

        assert expander.window == 5

    def test_default_max_results_is_80(self, mock_opensearch_client):
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index")

        assert expander.max_results == 80

    def test_builds_correct_batch_query(self, mock_opensearch_client, sample_results):
        """배치 쿼리 구조 검증"""
        mock_opensearch_client.search.return_value = {"hits": {"hits": []}}
        expander = NeighborChunkExpander(
            mock_opensearch_client, "test-index", window=2
        )

        expander.expand(sample_results)

        # search가 호출되었는지 확인
        mock_opensearch_client.search.assert_called_once()
        call_args = mock_opensearch_client.search.call_args

        # 인덱스 확인
        assert call_args.kwargs["index"] == "test-index"

        # 쿼리 구조 확인
        body = call_args.kwargs["body"]
        assert body["size"] == 80
        assert "bool" in body["query"]
        assert "should" in body["query"]["bool"]

        # should 절 개수 확인 (검색 결과 2개)
        should_clauses = body["query"]["bool"]["should"]
        assert len(should_clauses) == 2

        # 첫 번째 결과의 범위 확인 (document_id=1, chunk_index=5, window=2)
        first_clause = should_clauses[0]
        range_filter = first_clause["bool"]["filter"][1]["range"]["chunk_index"]
        assert range_filter["gte"] == 3  # max(0, 5-2)
        assert range_filter["lte"] == 7  # 5+2

    def test_merges_original_and_neighbors(self, mock_opensearch_client, sample_results):
        """원본과 이웃 병합"""
        # 이웃 청크 응답 Mock
        neighbor_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "chunk_1_4",
                        "_source": {
                            "document_id": 1,
                            "chunk_index": 4,
                            "content": "입사 1년차 직원의 경우...",
                        },
                    },
                    {
                        "_id": "chunk_1_6",
                        "_source": {
                            "document_id": 1,
                            "chunk_index": 6,
                            "content": "2년차부터는 16일로 증가합니다.",
                        },
                    },
                ]
            }
        }
        mock_opensearch_client.search.return_value = neighbor_response
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index", window=2)

        result = expander.expand(sample_results)

        # 원본 2개 + 이웃 2개 = 4개
        assert len(result) == 4

        # is_neighbor 필드 확인
        original_ids = {"chunk_1_5", "chunk_2_10"}
        for r in result:
            if r["_id"] in original_ids:
                assert r["is_neighbor"] is False
            else:
                assert r["is_neighbor"] is True

    def test_deduplicates_overlapping_neighbors(self, mock_opensearch_client):
        """중복 이웃 제거"""
        # 두 검색 결과가 같은 이웃을 공유하는 경우
        results = [
            {"_id": "c1", "_source": {"document_id": 1, "chunk_index": 5}},
            {"_id": "c2", "_source": {"document_id": 1, "chunk_index": 7}},
        ]
        # chunk_index 6은 둘 다의 이웃
        neighbor_response = {
            "hits": {
                "hits": [
                    {"_id": "c1", "_source": {"document_id": 1, "chunk_index": 5}},
                    {"_id": "n6", "_source": {"document_id": 1, "chunk_index": 6}},
                    {"_id": "c2", "_source": {"document_id": 1, "chunk_index": 7}},
                ]
            }
        }
        mock_opensearch_client.search.return_value = neighbor_response
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index", window=2)

        result = expander.expand(results)

        # 중복 없이 3개만 있어야 함
        ids = [r["_id"] for r in result]
        assert len(ids) == len(set(ids))  # 중복 없음

    def test_sorts_by_document_and_chunk_index(self, mock_opensearch_client):
        """문서별, 청크 순서대로 정렬"""
        results = [
            {"_id": "c2", "_source": {"document_id": 2, "chunk_index": 10}},
            {"_id": "c1", "_source": {"document_id": 1, "chunk_index": 5}},
        ]
        neighbor_response = {
            "hits": {
                "hits": [
                    {"_id": "n1", "_source": {"document_id": 1, "chunk_index": 4}},
                    {"_id": "n2", "_source": {"document_id": 2, "chunk_index": 11}},
                ]
            }
        }
        mock_opensearch_client.search.return_value = neighbor_response
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index")

        result = expander.expand(results)

        # 정렬 확인: document_id 오름차순, chunk_index 오름차순
        for i in range(len(result) - 1):
            curr = result[i]["_source"]
            next_ = result[i + 1]["_source"]
            curr_key = (curr.get("document_id", 0), curr.get("chunk_index", 0))
            next_key = (next_.get("document_id", 0), next_.get("chunk_index", 0))
            assert curr_key <= next_key

    def test_respects_max_results(self, mock_opensearch_client):
        """max_results 상한 적용"""
        results = [{"_id": "c1", "_source": {"document_id": 1, "chunk_index": 5}}]
        # 많은 이웃 반환
        neighbor_response = {
            "hits": {
                "hits": [
                    {"_id": f"n{i}", "_source": {"document_id": 1, "chunk_index": i}}
                    for i in range(100)
                ]
            }
        }
        mock_opensearch_client.search.return_value = neighbor_response
        expander = NeighborChunkExpander(
            mock_opensearch_client, "test-index", max_results=10
        )

        result = expander.expand(results)

        assert len(result) <= 10

    def test_handles_search_error_gracefully(self, mock_opensearch_client, sample_results, capsys):
        """검색 실패 시 원본 반환"""
        mock_opensearch_client.search.side_effect = Exception("Connection failed")
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index")

        result = expander.expand(sample_results)

        # 원본 그대로 반환
        assert result == sample_results

        # 경고 메시지 출력 확인
        captured = capsys.readouterr()
        assert "이웃 청크 조회 실패" in captured.out

    def test_handles_missing_document_id(self, mock_opensearch_client):
        """document_id 없는 결과 처리"""
        results = [
            {"_id": "c1", "_source": {"chunk_index": 5}},  # document_id 없음
        ]
        mock_opensearch_client.search.return_value = {"hits": {"hits": []}}
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index")

        result = expander.expand(results)

        # should 절이 없으므로 원본 반환
        assert result == results

    def test_handles_missing_chunk_index(self, mock_opensearch_client):
        """chunk_index 없는 결과 처리"""
        results = [
            {"_id": "c1", "_source": {"document_id": 1}},  # chunk_index 없음
        ]
        mock_opensearch_client.search.return_value = {"hits": {"hits": []}}
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index")

        result = expander.expand(results)

        # should 절이 없으므로 원본 반환
        assert result == results

    def test_window_zero_prevents_negative_index(self, mock_opensearch_client):
        """chunk_index가 0 근처일 때 음수 방지"""
        results = [
            {"_id": "c1", "_source": {"document_id": 1, "chunk_index": 1}},
        ]
        mock_opensearch_client.search.return_value = {"hits": {"hits": []}}
        expander = NeighborChunkExpander(
            mock_opensearch_client, "test-index", window=5
        )

        expander.expand(results)

        # 쿼리 확인
        body = mock_opensearch_client.search.call_args.kwargs["body"]
        range_filter = body["query"]["bool"]["should"][0]["bool"]["filter"][1]["range"]["chunk_index"]

        # gte는 0 이상이어야 함 (max(0, 1-5) = 0)
        assert range_filter["gte"] == 0
        assert range_filter["lte"] == 6  # 1+5

    def test_excludes_embedding_from_source(self, mock_opensearch_client, sample_results):
        """embedding 필드 제외 확인"""
        mock_opensearch_client.search.return_value = {"hits": {"hits": []}}
        expander = NeighborChunkExpander(mock_opensearch_client, "test-index")

        expander.expand(sample_results)

        body = mock_opensearch_client.search.call_args.kwargs["body"]
        assert body["_source"]["excludes"] == ["embedding"]


class TestChunkExpanderComparison:
    """확장기 비교 테스트"""

    def test_noop_returns_original(self, sample_results, mock_opensearch_client):
        """NoopChunkExpander는 원본 그대로"""
        noop = NoopChunkExpander()
        mock_opensearch_client.search.return_value = {
            "hits": {"hits": [{"_id": "neighbor", "_source": {"document_id": 1, "chunk_index": 4}}]}
        }
        neighbor = NeighborChunkExpander(mock_opensearch_client, "test-index")

        noop_result = noop.expand(sample_results)
        neighbor_result = neighbor.expand(sample_results)

        # Noop은 원본 그대로
        assert len(noop_result) == len(sample_results)
        # Neighbor는 확장됨
        assert len(neighbor_result) >= len(sample_results)
