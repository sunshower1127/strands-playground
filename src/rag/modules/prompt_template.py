"""프롬프트 템플릿 (PromptTemplate)

컨텍스트 + 질문 + 언어 설정 → LLM 프롬프트 생성.

설계 원칙:
    - System Prompt: 영어 (LLM 지시 이해력 최적화, 학습 데이터 92% 영어)
    - Context: 원본 언어 유지 (번역 시 정보 손실 방지)
    - User Prompt: 한국어 (자연스러운 UX, 응답 언어 유도)
    - 응답 언어: System + User 양쪽에서 이중 강조 (API 파라미터 없음)

권장 사용:
    StrictPromptTemplate()  # 할루시네이션 방지 + 출처 명시

참고:
    - 할루시네이션 감소: RAG + 명시적 지시로 42-68% 감소 가능 (2025 연구)
    - 다국어: 영어 System Prompt가 추론 성능 ~37% 더 좋음
    - 출처 형식: ContextBuilder가 생성한 [번호] (파일명, p.페이지) 형식 활용
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PromptTemplate(Protocol):
    """프롬프트 템플릿 프로토콜"""

    def render(
        self,
        context: str,
        question: str,
        response_language: str = "Korean",
    ) -> tuple[str, str]:
        """컨텍스트와 질문을 LLM 프롬프트로 변환

        Args:
            context: ContextBuilder가 생성한 컨텍스트 문자열
            question: 사용자 질문
            response_language: 응답 언어 (기본: Korean)

        Returns:
            (system_prompt, user_prompt) 튜플
        """
        ...


class SimplePromptTemplate:
    """단순 RAG 프롬프트 (베이스라인)

    최소한의 지시만 포함합니다.
    비교 기준용.

    출력 예시:
        system: "Answer the question based on the provided documents. Respond in Korean."
        user: "## Documents\n...\n\n## Question\n..."
    """

    def render(
        self,
        context: str,
        question: str,
        response_language: str = "Korean",
    ) -> tuple[str, str]:
        system = (
            f"Answer the question based on the provided documents. "
            f"Respond in {response_language}."
        )

        user = f"""## Documents
{context}

## Question
{question}"""

        return (system, user)


class StrictPromptTemplate:
    """문서 기반 엄격 프롬프트 (권장)

    할루시네이션 방지 + 출처 인용을 강제합니다.

    특징:
    1. 문서 기반 답변만 허용 (사전 지식 사용 금지)
    2. ContextBuilder가 생성한 출처 형식 인용 유도
    3. 답변 불가 시 명시적 응답
    4. 응답 언어 이중 강조 (System + User)

    출력 예시:
        system: "You are a document-based AI assistant..."
        user: "## 참고 문서\n...\n\n## 질문\n..."
    """

    SYSTEM = """You are a document-based AI assistant.

## Core Principles
1. Answer based ONLY on the provided documents.
2. NEVER use prior knowledge or make assumptions.
3. If information is not found, say: "해당 정보를 제공된 문서에서 찾을 수 없습니다."
4. Always cite sources using the document numbers or names provided (e.g., [1] or [문서명]).

## Prohibited
- Supplementing answers with general knowledge
- Presenting unverified information as fact
- Omitting source citations

## Response Language (CRITICAL)
You MUST respond in {response_language}. This is mandatory."""

    USER = """## 참고 문서
{context}

## 질문
{question}

위 문서를 기반으로 답변하세요. 각 정보의 출처를 문서 번호나 이름으로 명시하세요.
문서에서 답을 찾을 수 없으면 솔직히 말씀해주세요."""

    def render(
        self,
        context: str,
        question: str,
        response_language: str = "Korean",
    ) -> tuple[str, str]:
        system = self.SYSTEM.format(response_language=response_language)
        user = self.USER.format(context=context, question=question)
        return (system, user)
