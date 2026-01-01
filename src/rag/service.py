"""Basic RAG 서비스

고정 파이프라인 기반 RAG 서비스입니다.
RAGServiceBase 인터페이스를 구현합니다.

Usage:
    from src.rag import RAGService

    service = RAGService(project_id=334, pipeline="minimal")
    result = service.query("연차 휴가는 며칠인가요?")
"""

from src.types import RAGServiceBase, ServiceResult

from .pipeline import RAGPipeline, create_minimal_pipeline, create_standard_pipeline
from .types import RAGResult


class RAGService(RAGServiceBase):
    """Basic RAG 서비스

    고정 파이프라인을 사용하여 질문에 답변합니다.
    """

    def __init__(
        self,
        project_id: int = 334,
        pipeline: str = "minimal",
    ):
        """
        Args:
            project_id: 프로젝트 ID
            pipeline: 파이프라인 종류 ("minimal" | "standard")
        """
        self.project_id = project_id
        self._pipeline_type = pipeline
        self._pipeline: RAGPipeline | None = None

    @property
    def pipeline(self) -> RAGPipeline:
        """파이프라인 (lazy init)"""
        if self._pipeline is None:
            if self._pipeline_type == "standard":
                self._pipeline = create_standard_pipeline(project_id=self.project_id)
            else:
                self._pipeline = create_minimal_pipeline(project_id=self.project_id)
        return self._pipeline

    def query(self, question: str) -> ServiceResult:
        """질문에 대한 Basic RAG 실행

        Args:
            question: 사용자 질문

        Returns:
            ServiceResult: 통합 결과
        """
        result: RAGResult = self.pipeline.query(question)

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
