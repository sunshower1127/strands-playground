"""쿼리 빌더 (QueryBuilder)

전처리된 질문 + 임베딩 → OpenSearch 쿼리 생성

구현체:
- KNNQueryBuilder: 순수 벡터 검색 (베이스라인)
- HybridQueryBuilder: KNN + BM25 결합 (RRF 파이프라인)
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class QueryBuilder(Protocol):
    """쿼리 빌더 프로토콜"""

    def build(
        self,
        query: str,
        embedding: list[float],
        project_id: int,
        k: int = 5,
    ) -> dict:
        """OpenSearch 쿼리 생성

        Args:
            query: 전처리된 사용자 질문
            embedding: 질문 임베딩 벡터
            project_id: 프로젝트 ID (필터용)
            k: 반환할 문서 개수

        Returns:
            OpenSearch 쿼리 dict
        """
        ...


class KNNQueryBuilder:
    """순수 벡터 검색 (베이스라인)

    의미적 유사도만 사용. 디버깅 및 비교용.
    """

    def build(
        self,
        query: str,
        embedding: list[float],
        project_id: int,
        k: int = 5,
    ) -> dict:
        return {
            "query": {
                "knn": {
                    "embedding": {
                        "vector": embedding,
                        "k": k,
                        "filter": {"term": {"project_id": project_id}},
                    }
                }
            }
        }


class HybridQueryBuilder:
    """KNN + BM25 하이브리드 검색

    RRF (Reciprocal Rank Fusion) 파이프라인 사용.
    검색 시 search_pipeline="hybrid-rrf" 파라미터 필요.
    """

    # 검색 필드 및 가중치
    SEARCH_FIELDS = [
        "chunk_text^4.0",
        "text.ko^3.5",
        "text.en^1.8",
    ]

    # RRF 파이프라인 이름
    SEARCH_PIPELINE = "hybrid-rrf"

    def build(
        self,
        query: str,
        embedding: list[float],
        project_id: int,
        k: int = 5,
    ) -> dict:
        filter_clause = {"term": {"project_id": project_id}}

        # BM25 서브쿼리
        bm25_query = {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": self.SEARCH_FIELDS,
                        }
                    }
                ],
                "filter": [filter_clause],
            }
        }

        # KNN 서브쿼리
        knn_query = {
            "knn": {
                "embedding": {
                    "vector": embedding,
                    "k": k,
                    "filter": filter_clause,
                }
            }
        }

        return {
            "query": {
                "hybrid": {
                    "queries": [bm25_query, knn_query],
                }
            }
        }
