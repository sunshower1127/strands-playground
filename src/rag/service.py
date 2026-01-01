"""RAG 서비스 - 모드 전환 지원

Basic RAG와 Agent RAG를 통합하여 모드별 전환을 지원합니다.

Usage:
    from src.rag.service import RAGService

    service = RAGService(project_id=334)

    # Basic 모드 (기존 파이프라인)
    result = service.query("연차 휴가는 며칠인가요?", mode="basic")

    # Agent 모드 (Strands Agent)
    result = service.query("연차 휴가는 며칠인가요?", mode="agent")
"""

from dataclasses import dataclass, field
from typing import Literal

from .agent import AgentRAG, AgentRAGResult
from .pipeline import RAGPipeline, create_minimal_pipeline, create_standard_pipeline
from .types import RAGResult


# =============================================================================
# 통합 결과 타입
# =============================================================================


@dataclass
class ServiceResult:
    """RAG 서비스 통합 결과

    Basic/Agent 모드 공통 결과 형식입니다.

    Attributes:
        mode: 실행 모드 ("basic" | "agent")
        question: 원본 질문
        answer: 생성된 답변
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        latency_ms: 전체 소요 시간 (밀리초)
        model: 사용된 모델명
        sources: 검색된 소스 (Basic 모드)
        tool_calls: 도구 호출 정보 (Agent 모드)
        timings: 단계별 타이밍 (Basic 모드)
    """

    mode: str
    question: str
    answer: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""
    sources: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# =============================================================================
# RAG 서비스
# =============================================================================


class RAGService:
    """RAG 서비스 - Basic/Agent 모드 통합

    단일 인터페이스로 두 가지 RAG 모드를 지원합니다:
    - basic: 기존 파이프라인 (고정 흐름)
    - agent: Strands Agent (자율적 도구 호출)
    """

    def __init__(
        self,
        project_id: int = 334,
        basic_pipeline: str = "minimal",
    ):
        """
        Args:
            project_id: 프로젝트 ID
            basic_pipeline: Basic 모드 파이프라인 ("minimal" | "standard")
        """
        self.project_id = project_id

        # Basic 파이프라인 (lazy init)
        self._basic: RAGPipeline | None = None
        self._basic_pipeline = basic_pipeline

        # Agent (lazy init)
        self._agent: AgentRAG | None = None

    @property
    def basic(self) -> RAGPipeline:
        """Basic 파이프라인 (lazy init)"""
        if self._basic is None:
            if self._basic_pipeline == "standard":
                self._basic = create_standard_pipeline(project_id=self.project_id)
            else:
                self._basic = create_minimal_pipeline(project_id=self.project_id)
        return self._basic

    @property
    def agent(self) -> AgentRAG:
        """Agent RAG (lazy init)"""
        if self._agent is None:
            self._agent = AgentRAG(project_id=self.project_id)
        return self._agent

    def query(
        self,
        question: str,
        mode: Literal["basic", "agent"] = "basic",
    ) -> ServiceResult:
        """질문에 대한 RAG 실행

        Args:
            question: 사용자 질문
            mode: 실행 모드 ("basic" | "agent")

        Returns:
            ServiceResult: 통합 결과
        """
        if mode == "agent":
            return self._query_agent(question)
        else:
            return self._query_basic(question)

    def _query_basic(self, question: str) -> ServiceResult:
        """Basic 모드 실행"""
        result: RAGResult = self.basic.query(question)

        return ServiceResult(
            mode="basic",
            question=result.question,
            answer=result.answer,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model=result.model,
            sources=[
                {
                    "file_name": s["_source"].get("file_name", "unknown"),
                    "score": s.get("_score", 0),
                }
                for s in result.sources
            ],
            timings=result.timings,
        )

    def _query_agent(self, question: str) -> ServiceResult:
        """Agent 모드 실행"""
        result: AgentRAGResult = self.agent.query(question)

        return ServiceResult(
            mode="agent",
            question=result.question,
            answer=result.answer,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model=result.model,
            tool_calls=result.tool_calls,
        )


# =============================================================================
# 팩토리 함수
# =============================================================================


def create_rag_service(
    project_id: int = 334,
    basic_pipeline: str = "minimal",
) -> RAGService:
    """RAG 서비스 생성

    Args:
        project_id: 프로젝트 ID
        basic_pipeline: Basic 모드 파이프라인

    Returns:
        RAGService: RAG 서비스 인스턴스
    """
    return RAGService(project_id=project_id, basic_pipeline=basic_pipeline)
