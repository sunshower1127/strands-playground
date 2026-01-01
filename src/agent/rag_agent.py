"""Strands Agent RAG 파이프라인

Agent가 도구를 자율적으로 호출하여 RAG를 수행합니다.
기존 파이프라인과 달리 Agent가 검색 여부/횟수를 스스로 결정합니다.

Usage:
    from src.agent import AgentRAG

    agent_rag = AgentRAG(project_id=334)
    result = agent_rag.query("연차 휴가는 며칠인가요?")
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands.types.exceptions import MaxTokensReachedException

from .tools.search import clear_sources, get_call_history, get_last_sources, search_documents

logger = logging.getLogger(__name__)

load_dotenv()

# GCP 서비스 계정 인증 설정
_credentials_path = Path(__file__).parent.parent.parent / "credentials" / "gcp-service-account.json"
if _credentials_path.exists() and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_credentials_path)


# =============================================================================
# 타입 정의
# =============================================================================


@dataclass
class AgentRAGResult:
    """Agent RAG 파이프라인 결과

    Attributes:
        question: 원본 사용자 질문
        answer: Agent 생성 답변
        tool_calls: 도구 호출 목록 [{"name": str, "args": dict}, ...]
        tool_call_count: 도구 호출 횟수
        input_tokens: LLM 입력 토큰 수
        output_tokens: LLM 출력 토큰 수
        latency_ms: 전체 파이프라인 소요 시간 (밀리초)
        model: 사용된 LLM 모델명
        sources: 검색된 소스 목록 [{"file_name": str, "score": float, "query": str}, ...]
        timings: 단계별 타이밍 {"total": float, "tool_calls": float, "llm": float}
        call_history: 도구 호출 이력 [{"call_index": int, "tool": str, "query": str, ...}, ...]
    """

    question: str
    answer: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""
    sources: list[dict] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    call_history: list[dict] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        """총 토큰 수"""
        return self.input_tokens + self.output_tokens


# =============================================================================
# Agent 시스템 프롬프트
# =============================================================================

AGENT_SYSTEM_PROMPT = """당신은 문서 검색 및 질문 답변 전문가입니다.

사용자의 질문에 답하기 위해 다음 도구를 사용할 수 있습니다:
- search_documents: 관련 문서 검색

답변 가이드라인:
1. 먼저 질문을 분석하여 필요한 정보를 파악하세요
2. search_documents 도구로 관련 문서를 검색하세요
3. 검색 결과가 불충분하면 다른 키워드로 재검색하세요
4. 검색된 문서를 바탕으로 정확하게 답변하세요
5. 문서에 없는 내용은 추측하지 마세요 - "문서에서 해당 정보를 찾을 수 없습니다"라고 답하세요
6. 답변할 때 근거가 된 문서를 언급하세요
"""


# =============================================================================
# Agent RAG 클래스
# =============================================================================


class AgentRAG:
    """Strands Agent 기반 RAG 파이프라인

    Agent가 검색 도구를 자율적으로 호출하여 질문에 답변합니다.
    """

    def __init__(
        self,
        project_id: int = 334,
        model_id: str | None = None,
    ):
        """
        Args:
            project_id: 프로젝트 ID (검색 필터용)
            model_id: LiteLLM 모델 ID (기본: vertex_ai/claude-sonnet-4-5@20250929)
        """
        self.project_id = project_id

        # Vertex AI 모델 ID 형식: vertex_ai/claude-sonnet-4-5@20250929
        self.model_id = model_id or os.getenv(
            "LITELLM_MODEL_ID",
            "vertex_ai/claude-sonnet-4-5@20250929",
        )

        # LiteLLM 모델 설정 (Vertex AI)
        self.model = LiteLLMModel(
            model_id=self.model_id,
            params={
                "vertex_project": os.getenv("GCP_PROJECT_ID"),
                "vertex_location": os.getenv("GCP_REGION", "us-east5"),
                "max_tokens": 2048,
            },
        )

        # Agent 생성
        self.agent = Agent(
            model=self.model,
            system_prompt=AGENT_SYSTEM_PROMPT,
            tools=[search_documents],
        )

    def query(self, question: str) -> AgentRAGResult:
        """질문에 대한 Agent RAG 실행

        Args:
            question: 사용자 질문

        Returns:
            AgentRAGResult: 답변, 도구 호출 정보, 토큰 수, 레이턴시 등
        """
        start = time.time()

        # 검색 결과 초기화
        clear_sources()

        try:
            # Agent 호출 - 반환 타입: AgentResult
            # AgentResult 필드: stop_reason, message, metrics, state, interrupts, structured_output
            result = self.agent(question)

            elapsed_ms = (time.time() - start) * 1000

            # 검색 결과 및 호출 이력 수집
            sources = get_last_sources()
            call_history = get_call_history()

            # 도구 호출 정보 추출 (metrics.tool_metrics에서)
            # ToolMetrics 필드: tool, call_count, success_count, error_count, total_time
            tool_calls = []
            tool_time_ms = 0.0
            if result.metrics and result.metrics.tool_metrics:
                for tool_name, tool_metric in result.metrics.tool_metrics.items():
                    tool_calls.append({
                        "name": tool_name,
                        "count": tool_metric.call_count,
                        "success": tool_metric.success_count,
                        "error": tool_metric.error_count,
                    })
                    # 도구 호출 시간 추출
                    if hasattr(tool_metric, "total_time") and tool_metric.total_time:
                        tool_time_ms += tool_metric.total_time * 1000

            # 타이밍 계산
            timings = {
                "total": round(elapsed_ms, 1),
                "tool_calls": round(tool_time_ms, 1),
                "llm": round(max(0, elapsed_ms - tool_time_ms), 1),
            }

            # 토큰 사용량 추출 (metrics.accumulated_usage에서)
            # Usage: {"inputTokens": int, "outputTokens": int, "totalTokens": int}
            input_tokens = 0
            output_tokens = 0
            if result.metrics and result.metrics.accumulated_usage:
                usage = result.metrics.accumulated_usage
                input_tokens = usage.get("inputTokens", 0)
                output_tokens = usage.get("outputTokens", 0)
                total_used = input_tokens + output_tokens
                logger.debug(f"Token usage: {total_used} (input={input_tokens}, output={output_tokens})")

            # 답변 텍스트 추출 (message.content에서)
            # Message는 {"role": str, "content": [{"text": "..."}, ...]} 형태
            answer = ""
            if result.message:
                content_blocks = result.message.get("content", [])
                for block in content_blocks:
                    if isinstance(block, dict) and "text" in block:
                        answer += block["text"]

            return AgentRAGResult(
                question=question,
                answer=answer,
                tool_calls=tool_calls,
                tool_call_count=len(tool_calls),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=round(elapsed_ms, 1),
                model=self.model_id,
                sources=sources,
                timings=timings,
                call_history=call_history,
            )

        except MaxTokensReachedException as e:
            elapsed_ms = (time.time() - start) * 1000
            sources = get_last_sources()
            call_history = get_call_history()

            logger.warning(f"MaxTokensReachedException: {question[:50]}...")
            logger.warning(f"Sources before error: {len(sources)}")

            return AgentRAGResult(
                question=question,
                answer=f"ERROR: {e!s}",
                tool_calls=[],
                tool_call_count=0,
                input_tokens=0,
                output_tokens=0,
                latency_ms=round(elapsed_ms, 1),
                model=self.model_id,
                sources=sources,
                timings={"total": round(elapsed_ms, 1), "error": "max_tokens"},
                call_history=call_history,
            )


# =============================================================================
# 팩토리 함수
# =============================================================================


def create_agent_rag(project_id: int = 334) -> AgentRAG:
    """Agent RAG 파이프라인 생성

    Args:
        project_id: 프로젝트 ID

    Returns:
        AgentRAG: Agent RAG 인스턴스
    """
    return AgentRAG(project_id=project_id)
