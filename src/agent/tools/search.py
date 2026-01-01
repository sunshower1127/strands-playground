"""OpenSearch 검색 도구

Strands Agent에서 사용할 문서 검색 도구입니다.
"""

import logging
import time

from strands import tool

from src.embedding_client import EmbeddingClient
from src.opensearch_client import OpenSearchClient

logger = logging.getLogger(__name__)

# 싱글턴 클라이언트 (Agent 내에서 재사용)
_opensearch_client: OpenSearchClient | None = None
_embedding_client: EmbeddingClient | None = None

# 검색 결과 저장 (Agent 호출 간 공유)
_last_search_sources: list[dict] = []

# 도구 호출 이력 저장
_call_history: list[dict] = []


def get_last_sources() -> list[dict]:
    """마지막 검색 소스 반환"""
    return _last_search_sources.copy()


def clear_sources() -> None:
    """검색 소스 초기화"""
    global _last_search_sources, _call_history
    _last_search_sources = []
    _call_history = []


def get_call_history() -> list[dict]:
    """도구 호출 이력 반환"""
    return _call_history.copy()


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
    global _last_search_sources, _call_history

    call_start = time.time()
    call_index = len(_call_history) + 1

    logger.info(f"[Call #{call_index}] search_documents(query='{query}', k={k})")

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

    elapsed_ms = (time.time() - call_start) * 1000

    if not results:
        # 호출 이력 저장 (결과 없음)
        _call_history.append({
            "call_index": call_index,
            "tool": "search_documents",
            "query": query,
            "k": k,
            "elapsed_ms": round(elapsed_ms, 1),
            "result_count": 0,
            "documents": [],
        })
        logger.info(f"[Call #{call_index}] No results ({elapsed_ms:.1f}ms)")
        return "검색 결과가 없습니다."

    # 결과 포맷팅 및 소스 저장
    output = []
    documents = []
    for i, hit in enumerate(results, 1):
        source = hit["_source"]
        score = hit.get("_score", 0)
        file_name = source.get("file_name", "unknown")
        text = source.get("text", "")

        # 검색 결과 저장 (sources용)
        _last_search_sources.append({
            "file_name": file_name,
            "score": round(score, 6),
            "query": query,
        })

        # 호출 이력용 문서 정보
        documents.append({
            "rank": i,
            "file_name": file_name,
            "score": round(score, 4),
            "text_preview": text[:100] + "..." if len(text) > 100 else text,
        })

        output.append(f"[문서 {i}] ({file_name}, 점수: {score:.3f})\n{text}")

    # 호출 이력 저장
    _call_history.append({
        "call_index": call_index,
        "tool": "search_documents",
        "query": query,
        "k": k,
        "elapsed_ms": round(elapsed_ms, 1),
        "result_count": len(results),
        "documents": documents,
    })

    logger.info(f"[Call #{call_index}] Found {len(results)} docs ({elapsed_ms:.1f}ms)")

    return "\n\n---\n\n".join(output)
