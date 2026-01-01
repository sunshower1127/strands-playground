"""RAG 파이프라인 타입 정의"""

from dataclasses import dataclass, field


@dataclass
class RAGResult:
    """RAG 파이프라인 결과

    Attributes:
        question: 원본 사용자 질문
        answer: LLM 생성 답변
        sources: 검색된 문서 리스트 [{"_id": str, "_score": float, "_source": {...}}, ...]
        input_tokens: LLM 입력 토큰 수
        output_tokens: LLM 출력 토큰 수
        latency_ms: 전체 파이프라인 소요 시간 (밀리초)
        model: 사용된 LLM 모델명
        timings: 단계별 소요 시간 (밀리초) {"embedding": 100.5, "search": 50.2, ...}
    """

    question: str
    answer: str
    sources: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def source_count(self) -> int:
        """검색된 문서 개수"""
        return len(self.sources)

    @property
    def total_tokens(self) -> int:
        """총 토큰 수"""
        return self.input_tokens + self.output_tokens
