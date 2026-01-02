"""통합 Agent

세션 기반 대화형 Agent입니다.
모드 전환(normal/agent)을 지원하며, 세션 컨텍스트를 유지합니다.
"""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models.litellm import LiteLLMModel
from strands.session.file_session_manager import FileSessionManager

from strands_tools.tavily import tavily_search

from .tools.ask_user import ask_user
from .tools.search import search_documents

load_dotenv()

# GCP 서비스 계정 인증 설정
_credentials_path = Path(__file__).parent.parent.parent / "credentials" / "gcp-service-account.json"
if _credentials_path.exists() and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_credentials_path)


# =============================================================================
# 시스템 프롬프트
# =============================================================================

NORMAL_PROMPT = """당신은 친절한 AI 어시스턴트입니다.
사용자의 질문에 간결하고 정확하게 답변하세요.
"""

AGENT_PROMPT = """당신은 문서 검색 및 질문 답변 전문가입니다.

사용 가능한 도구:
- search_documents: 내부 문서 검색 (회사 정책, 제품 가이드 등)
- tavily_search: 외부 웹 검색 (법률, 트렌드, 경쟁사 정보 등)
- ask_user: 질문이 불명확하거나 추가 정보가 필요할 때 사용자에게 질문

도구 선택 가이드:
- 회사 내부 정보 → search_documents
- 외부 정보 (법률, 시장 동향, 경쟁사) → tavily_search
- 내부 정책과 외부 기준 비교 → 둘 다 사용

답변 가이드라인:
1. 먼저 질문을 분석하여 필요한 정보를 파악하세요
2. 적절한 도구로 관련 정보를 검색하세요
3. 검색 시 완전한 문장으로 검색하세요 (예: "입사 1년차의 연차 일수는?" O, "1년차 연차" X)
4. 검색 결과가 불충분하면 질문을 다른 관점에서 재구성하여 검색하세요
5. 질문이 불명확하면 ask_user로 명확화 질문을 하세요
6. 정보가 없는 경우 "해당 정보를 찾을 수 없습니다"라고 답하세요
7. 답변할 때 정보 출처를 언급하세요 (내부 문서명 또는 웹 출처)
"""


# =============================================================================
# 통합 Agent 클래스
# =============================================================================


class UnifiedAgent:
    """세션 기반 통합 Agent

    - 세션 관리: FileSessionManager로 대화 히스토리 저장
    - 컨텍스트 관리: SlidingWindowConversationManager로 토큰 제한 대응
    - 모드 전환: normal(저렴) / agent(고급)
    """

    def __init__(
        self,
        session_manager: FileSessionManager,
        project_id: int = 334,
        window_size: int = 20,
    ):
        """
        Args:
            session_manager: 세션 관리자 (외부에서 주입)
            project_id: 프로젝트 ID (검색 필터용)
            window_size: 컨텍스트 윈도우 크기
        """
        self.session_manager = session_manager
        self.project_id = project_id

        # 컨텍스트 관리자 (JetBrains Research 2025: Sliding Window 권장)
        self.conversation_manager = SlidingWindowConversationManager(
            window_size=window_size,
            should_truncate_results=True,
        )

        # 모드별 설정
        self._mode_configs = {
            "normal": {
                "model_id": "vertex_ai/claude-3-5-haiku@20241022",
                "tools": [],
                "prompt": NORMAL_PROMPT,
            },
            "agent": {
                "model_id": os.getenv("LITELLM_MODEL_ID", "vertex_ai/claude-sonnet-4-5@20250929"),
                "tools": [search_documents, tavily_search, ask_user],
                "prompt": AGENT_PROMPT,
            },
        }

        self._current_mode = "agent"
        self._agent: Agent | None = None

    def set_mode(self, mode: Literal["normal", "agent"]) -> None:
        """모드 전환 (세션 유지, Agent만 재생성)"""
        if mode not in self._mode_configs:
            raise ValueError(f"Unknown mode: {mode}")
        self._current_mode = mode
        self._agent = None  # 다음 호출 시 재생성

    def _get_or_create_agent(self) -> Agent:
        """현재 모드에 맞는 Agent 반환 (lazy 생성)"""
        if self._agent is not None:
            return self._agent

        config = self._mode_configs[self._current_mode]

        model = LiteLLMModel(
            model_id=config["model_id"],
            params={
                "vertex_project": os.getenv("GCP_PROJECT_ID"),
                "vertex_location": os.getenv("GCP_REGION", "us-east5"),
                "max_tokens": 2048,
            },
        )

        self._agent = Agent(
            model=model,
            session_manager=self.session_manager,
            conversation_manager=self.conversation_manager,
            tools=config["tools"],
            system_prompt=config["prompt"],
        )

        return self._agent

    def query(self, question: str):
        """질문 처리 (interrupt 포함)

        Returns:
            AgentResult: stop_reason이 "interrupt"면 추가 처리 필요
        """
        agent = self._get_or_create_agent()
        return agent(question)

    def resume(self, responses: list[dict]):
        """Interrupt 응답 후 재개

        Args:
            responses: [{"interruptResponse": {"interruptId": ..., "response": ...}}]
        """
        agent = self._get_or_create_agent()
        return agent(responses)

    @property
    def current_mode(self) -> str:
        return self._current_mode
