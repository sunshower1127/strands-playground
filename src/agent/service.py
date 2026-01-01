"""Agent RAG 서비스

Strands Agent 기반 RAG 서비스입니다.
RAGServiceBase 인터페이스를 구현합니다.

Usage:
    from src.agent import AgentRAGService

    service = AgentRAGService(project_id=334)
    result = service.query("연차 휴가는 며칠인가요?")
"""

from src.types import RAGServiceBase, ServiceResult

from .rag_agent import AgentRAG


class AgentRAGService(RAGServiceBase):
    """Agent RAG 서비스

    Strands Agent가 검색 도구를 자율적으로 호출하여 질문에 답변합니다.
    매 쿼리마다 새 Agent를 생성하여 대화 히스토리가 누적되지 않습니다.
    """

    def __init__(self, project_id: int = 334):
        """
        Args:
            project_id: 프로젝트 ID (검색 필터용)
        """
        self.project_id = project_id

    def query(self, question: str) -> ServiceResult:
        """질문에 대한 Agent RAG 실행

        매번 새 Agent를 생성하여 stateless하게 동작합니다.
        (Strands Agent는 기본적으로 대화 히스토리를 유지하므로
        재사용 시 토큰이 기하급수적으로 증가함)

        Args:
            question: 사용자 질문

        Returns:
            ServiceResult: 통합 결과
        """
        # 매번 새 Agent 생성 (stateless)
        agent = AgentRAG(project_id=self.project_id)
        result = agent.query(question)

        return ServiceResult(
            mode="agent",
            question=result.question,
            answer=result.answer,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model=result.model,
            tool_calls=result.tool_calls,
            sources=result.sources,
            timings=result.timings,
            call_history=result.call_history,
        )
