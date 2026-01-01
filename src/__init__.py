"""strands-playground

RAG 시스템 실험 프로젝트입니다.

Usage:
    from src import create_service

    # Basic RAG
    service = create_service(mode="basic")

    # Agent RAG
    service = create_service(mode="agent")

    result = service.query("연차 휴가는 며칠인가요?")
"""

from .service import create_service
from .types import RAGServiceBase, ServiceResult

__all__ = [
    "create_service",
    "RAGServiceBase",
    "ServiceResult",
]
