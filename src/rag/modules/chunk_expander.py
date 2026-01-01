"""청크 확장기 (ChunkExpander)

검색 결과의 이웃 청크를 확장하여 컨텍스트 완전성을 확보합니다.

파이프라인 위치:
    검색 → ResultFilter (Rerank) → ChunkExpander → ContextBuilder

권장 사용:
    expander = NeighborChunkExpander(client, "rag-index", window=5)
    expanded = expander.expand(reranked_results)
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ChunkExpander(Protocol):
    """청크 확장기 프로토콜"""

    def expand(self, results: list[dict]) -> list[dict]:
        """검색 결과에 이웃 청크 추가

        Args:
            results: 검색 결과 리스트 (Rerank 후 Top-K)
                     [{"_id": str, "_source": {"document_id": int, "chunk_index": int, ...}, ...}, ...]

        Returns:
            원본 + 이웃 청크가 포함된 확장 리스트
            각 결과에 "is_neighbor" 필드 추가됨
        """
        ...


class NoopChunkExpander:
    """확장 안 함 (베이스라인)

    검색 결과를 그대로 반환합니다.
    비교 기준용.
    """

    def expand(self, results: list[dict]) -> list[dict]:
        return results


class NeighborChunkExpander:
    """이웃 청크 배치 조회로 확장

    검색된 청크의 앞뒤 N개 청크를 한 번의 배치 쿼리로 조회합니다.

    Args:
        opensearch_client: OpenSearch 클라이언트
        index_name: 인덱스 이름
        window: 앞뒤 청크 확장 범위 (기본값: 5)
        max_results: 최대 반환 결과 수 (기본값: 80)

    Example:
        expander = NeighborChunkExpander(client, "rag-index", window=5)
        expanded = expander.expand(results)
        # chunk_index 10인 결과 → 5~15 범위 청크 포함
    """

    def __init__(
        self,
        opensearch_client: Any,
        index_name: str,
        window: int = 5,
        max_results: int = 80,
    ):
        self.client = opensearch_client
        self.index = index_name
        self.window = window
        self.max_results = max_results

    def expand(self, results: list[dict]) -> list[dict]:
        if not results:
            return results

        # 1. 모든 이웃 조건을 한 번에 수집
        should_clauses = []
        for r in results:
            source = r.get("_source", {})
            doc_id = source.get("document_id")
            chunk_idx = source.get("chunk_index")

            if doc_id is not None and chunk_idx is not None:
                should_clauses.append(
                    {
                        "bool": {
                            "filter": [
                                {"term": {"document_id": doc_id}},
                                {
                                    "range": {
                                        "chunk_index": {
                                            "gte": max(0, chunk_idx - self.window),
                                            "lte": chunk_idx + self.window,
                                        }
                                    }
                                },
                            ]
                        }
                    }
                )

        if not should_clauses:
            return results

        # 2. 한 번의 배치 쿼리로 모든 이웃 조회
        body = {
            "size": self.max_results,
            "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
            "_source": {"excludes": ["embedding"]},
            "sort": [{"document_id": "asc"}, {"chunk_index": "asc"}],
        }

        try:
            response = self.client.search(index=self.index, body=body)
            neighbor_hits = response.get("hits", {}).get("hits", [])
        except Exception as e:
            print(f"⚠️ 이웃 청크 조회 실패: {e}")
            return results

        # 3. 원본 + 이웃 병합 (중복 제거)
        return self._merge_results(results, neighbor_hits)

    def _merge_results(
        self,
        originals: list[dict],
        neighbors: list[dict],
    ) -> list[dict]:
        """원본과 이웃 병합, 중복 제거, 정렬"""
        seen: set[str] = set()
        merged: list[dict] = []

        # 원본 먼저 추가 (is_neighbor=False)
        for r in originals:
            chunk_id = r.get("_id")
            if chunk_id and chunk_id not in seen:
                r["is_neighbor"] = False
                merged.append(r)
                seen.add(chunk_id)

        # 이웃 추가 (is_neighbor=True)
        for r in neighbors:
            chunk_id = r.get("_id")
            if chunk_id and chunk_id not in seen:
                r["is_neighbor"] = True
                merged.append(r)
                seen.add(chunk_id)

        # 문서별, 청크 순서대로 정렬
        merged.sort(
            key=lambda x: (
                x.get("_source", {}).get("document_id", 0),
                x.get("_source", {}).get("chunk_index", 0),
            )
        )

        # 상한 적용
        if len(merged) > self.max_results:
            merged = merged[: self.max_results]

        return merged
