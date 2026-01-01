"""공통 타입 정의

RAG 서비스의 공통 인터페이스와 결과 타입을 정의합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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
        call_history: 도구 호출 상세 이력 (Agent 모드)
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
    call_history: list[dict] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class RAGServiceBase(ABC):
    """RAG 서비스 기본 인터페이스

    Basic RAG와 Agent RAG가 공통으로 구현하는 인터페이스입니다.
    """

    @abstractmethod
    def query(self, question: str) -> ServiceResult:
        """질문에 대한 RAG 실행

        Args:
            question: 사용자 질문

        Returns:
            ServiceResult: 통합 결과
        """
        pass
