"""OpenSearch 검색 도구

Strands Agent에서 사용할 문서 검색 도구입니다.
"""

from strands import tool

from src.embedding_client import EmbeddingClient
from src.opensearch_client import OpenSearchClient

# 싱글턴 클라이언트 (Agent 내에서 재사용)
_opensearch_client: OpenSearchClient | None = None
_embedding_client: EmbeddingClient | None = None


def _get_clients() -> tuple[OpenSearchClient, EmbeddingClient]:
    """클라이언트 싱글턴 반환"""
    global _opensearch_client, _embedding_client
    if _opensearch_client is None:
        _opensearch_client = OpenSearchClient()
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _opensearch_client, _embedding_client


@tool
def search_documents(
    query: str,
    k: int = 5,
    project_id: int = 334,
) -> str:
    """OpenSearch에서 관련 문서를 검색합니다.

    사용자 질문에 답하기 위해 관련 문서를 검색할 때 사용합니다.
    검색 결과가 불충분하면 다른 키워드로 재검색할 수 있습니다.

    Args:
        query: 검색할 질문 또는 키워드
        k: 반환할 문서 개수 (기본값: 5)
        project_id: 프로젝트 ID (기본값: 334)

    Returns:
        검색된 문서들의 내용 (문서별 구분자로 분리)
    """
    opensearch, embedding = _get_clients()

    # 임베딩 생성
    vector = embedding.embed(query)

    # KNN 쿼리 생성
    search_query = {
        "query": {
            "bool": {
                "must": [{"knn": {"embedding": {"vector": vector, "k": k}}}],
                "filter": [{"term": {"project_id": project_id}}],
            }
        }
    }

    # 검색 실행
    results = opensearch.search(
        index="rag-index-fargate-live",
        query=search_query,
        size=k,
    )

    if not results:
        return "검색 결과가 없습니다."

    # 결과 포맷팅
    output = []
    for i, hit in enumerate(results, 1):
        source = hit["_source"]
        score = hit.get("_score", 0)
        file_name = source.get("file_name", "unknown")
        text = source.get("text", "")

        output.append(f"[문서 {i}] ({file_name}, 점수: {score:.3f})\n{text}")

    return "\n\n---\n\n".join(output)
