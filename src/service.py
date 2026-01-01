"""RAG 서비스 헬퍼

Basic/Agent 모드 간 전환을 쉽게 해주는 팩토리 함수입니다.

Usage:
    from src import create_service

    # Basic 모드
    service = create_service(mode="basic")
    result = service.query("연차 휴가는 며칠인가요?")

    # Agent 모드
    service = create_service(mode="agent")
    result = service.query("연차 휴가는 며칠인가요?")
"""

from typing import Literal

from .types import RAGServiceBase


def create_service(
    mode: Literal["basic", "agent"] = "basic",
    project_id: int = 334,
    **kwargs,
) -> RAGServiceBase:
    """RAG 서비스 생성

    Args:
        mode: 서비스 모드 ("basic" | "agent")
        project_id: 프로젝트 ID
        **kwargs: 추가 설정
            - pipeline: Basic 모드 파이프라인 ("minimal" | "standard")

    Returns:
        RAGServiceBase: RAG 서비스 인스턴스
    """
    if mode == "agent":
        from .agent import AgentRAGService

        return AgentRAGService(project_id=project_id)
    else:
        from .rag import RAGService

        pipeline = kwargs.get("pipeline", "minimal")
        return RAGService(project_id=project_id, pipeline=pipeline)
