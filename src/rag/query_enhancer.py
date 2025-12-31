"""쿼리 개선기 (QueryEnhancer) - 대화 히스토리를 활용한 쿼리 개선

대화 히스토리를 활용하여 모호한 질문을 명확한 검색 쿼리로 개선한다.
예: "그건 어떻게 작동해?" + 히스토리 → "Gemini API 작동 방식"
"""

from typing import Protocol


class QueryEnhancer(Protocol):
    """쿼리 개선기 프로토콜"""

    def enhance(
        self,
        query: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        대화 히스토리를 활용해 쿼리 개선

        Args:
            query: 현재 사용자 질문
            history: 대화 히스토리 [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            개선된 쿼리 (또는 원본)
        """
        ...


class NoopQueryEnhancer:
    """쿼리 개선 안 함 - 원본 그대로 반환 (베이스라인)"""

    def enhance(
        self,
        query: str,
        history: list[dict] | None = None,
    ) -> str:
        """원본 쿼리 그대로 반환"""
        return query


class LLMQueryEnhancer:
    """LLM 기반 쿼리 개선 (기존 Flash 로직 포팅)

    기존 프로젝트의 analyze_context_with_flash() 로직을 포팅.
    - 최근 6개 메시지 사용 (user-assistant 3쌍)
    - 메시지당 300자 제한 (토큰 절약)
    - 히스토리 없으면 스킵
    """

    SYSTEM_PROMPT = """You are a query rewriter for a document search system.
Your task is to rewrite ambiguous queries into clear search queries."""

    USER_PROMPT_TEMPLATE = """Recent conversation:
{context}

Current question: "{query}"

Instructions:
1. If the question contains pronouns or references to previous context:
   - Replace them with specific terms from the conversation
   - Example: "그건 어떻게 작동해?" → "Gemini API 작동 방식"
   - Example: "더 자세히 알려줘" → "연차 휴가 정책 상세 내용"

2. If it's an independent question:
   - Return the original question as-is

Return ONLY the rewritten query, nothing else."""

    def __init__(
        self,
        llm_client,  # GeminiClient 또는 다른 LLM 클라이언트
        max_history: int = 6,
        max_content_length: int = 300,
    ):
        """
        Args:
            llm_client: LLM 클라이언트 (call 메서드 필요)
            max_history: 사용할 최대 히스토리 메시지 수 (기본 6개)
            max_content_length: 메시지당 최대 길이 (기본 300자)
        """
        self.llm = llm_client
        self.max_history = max_history
        self.max_content_length = max_content_length

    def enhance(
        self,
        query: str,
        history: list[dict] | None = None,
    ) -> str:
        """대화 히스토리를 활용해 쿼리 개선"""
        # 스킵 조건 1: 히스토리 없음
        if not history or len(history) == 0:
            return query

        # 스킵 조건 2: 현재 메시지만 있음 (첫 질문)
        if len(history) == 1:
            return query

        # 최근 N개 메시지만 사용
        recent = history[-self.max_history :]

        # 컨텍스트 구성 (길이 제한)
        context = self._build_context(recent)

        # LLM 호출
        try:
            user_prompt = self.USER_PROMPT_TEMPLATE.format(context=context, query=query)
            response = self.llm.call(
                prompt=user_prompt,
                system=self.SYSTEM_PROMPT,
                max_tokens=256,
            )
            enhanced = response.content.strip()
            return enhanced if enhanced else query
        except Exception as e:
            print(f"⚠️ QueryEnhancer 실패, 원본 반환: {e}")
            return query

    def _build_context(self, messages: list[dict]) -> str:
        """히스토리를 컨텍스트 문자열로 변환"""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # 길이 제한
            if len(content) > self.max_content_length:
                content = content[: self.max_content_length] + "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
