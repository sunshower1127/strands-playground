"""RAG 파이프라인

모든 컴포넌트를 조립하여 E2E 파이프라인을 구성합니다.

Usage:
    from src.rag.pipeline import create_minimal_pipeline, create_full_pipeline

    # 최소 구성 (벡터 검색만)
    pipeline = create_minimal_pipeline(project_id=334)
    result = pipeline.query("연차 휴가는 며칠인가요?")

    # 전체 구성 (하이브리드 + 리랭킹)
    pipeline = create_full_pipeline(project_id=334)
    result = pipeline.query("연차 휴가는 며칠인가요?")
"""

import time

from src.embedding_client import EmbeddingClient
from src.llm_client import LLMClient
from src.opensearch_client import OpenSearchClient

from .chunk_expander import ChunkExpander, NeighborChunkExpander, NoopChunkExpander
from .context_builder import ContextBuilder, RankedContextBuilder, SimpleContextBuilder
from .preprocessor import KoreanPreprocessor, NoopPreprocessor, Preprocessor
from .prompt_template import PromptTemplate, SimplePromptTemplate, StrictPromptTemplate
from .query_builder import HybridQueryBuilder, KNNQueryBuilder, QueryBuilder
from .query_enhancer import NoopQueryEnhancer, QueryEnhancer
from .result_filter import (
    CompositeFilter,
    NoopFilter,
    RerankerFilter,
    ResultFilter,
    TopKFilter,
)
from .types import RAGResult


class RAGPipeline:
    """RAG 파이프라인

    검색 → 필터링 → 확장 → 컨텍스트 생성 → LLM 호출까지
    전체 파이프라인을 조립합니다.

    파이프라인 흐름:
        1. 쿼리 개선 (선택) - 대화 히스토리 기반 질문 명확화
        2. 전처리 (선택) - 질문 정규화
        3. 임베딩 생성 - 질문 벡터화
        4. 검색 쿼리 생성 - KNN 또는 하이브리드
        5. 검색 실행 - OpenSearch 호출
        6. 결과 필터링 (선택) - Top-K, Reranking 등
        7. 청크 확장 (선택) - 이웃 청크 추가
        8. 컨텍스트 생성 - LLM 주입용 문자열
        9. 프롬프트 생성 - System/User 프롬프트
        10. LLM 호출 - 답변 생성
    """

    def __init__(
        self,
        # 필수 클라이언트
        search_client: OpenSearchClient,
        embedding_client: EmbeddingClient,
        llm_client: LLMClient,
        # 조립 가능한 컴포넌트
        query_builder: QueryBuilder,
        context_builder: ContextBuilder,
        prompt_template: PromptTemplate,
        preprocessor: Preprocessor | None = None,
        query_enhancer: QueryEnhancer | None = None,
        result_filter: ResultFilter | None = None,
        chunk_expander: ChunkExpander | None = None,
        # 설정
        index: str = "rag-index-fargate-live",
        project_id: int = 334,
        search_size: int = 20,
        search_pipeline: str | None = None,
    ):
        """
        Args:
            search_client: OpenSearch 클라이언트
            embedding_client: 임베딩 클라이언트
            llm_client: LLM 클라이언트
            query_builder: 검색 쿼리 빌더
            context_builder: 컨텍스트 빌더
            prompt_template: 프롬프트 템플릿
            preprocessor: 쿼리 전처리기 (선택)
            query_enhancer: 쿼리 개선기 (선택) - 대화 히스토리 기반
            result_filter: 결과 필터 (선택)
            chunk_expander: 청크 확장기 (선택)
            index: OpenSearch 인덱스명
            project_id: 프로젝트 ID (필터용)
            search_size: 검색 결과 개수
            search_pipeline: OpenSearch 검색 파이프라인 (예: "hybrid-rrf")
        """
        self.search_client = search_client
        self.embedding_client = embedding_client
        self.llm_client = llm_client

        self.query_builder = query_builder
        self.context_builder = context_builder
        self.prompt_template = prompt_template
        self.preprocessor = preprocessor
        self.query_enhancer = query_enhancer
        self.result_filter = result_filter
        self.chunk_expander = chunk_expander

        self.index = index
        self.project_id = project_id
        self.search_size = search_size
        self.search_pipeline = search_pipeline

    def query(
        self,
        question: str,
        history: list[dict] | None = None,
    ) -> RAGResult:
        """질문에 대한 RAG 파이프라인 실행

        Args:
            question: 사용자 질문
            history: 대화 히스토리 (선택) - [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            RAGResult: 답변, 출처, 토큰 수, 레이턴시, 단계별 타이밍 등
        """
        start = time.time()
        timings: dict[str, float] = {}

        def _measure(name: str):
            """단계별 시간 측정 헬퍼"""
            nonlocal start
            now = time.time()
            timings[name] = round((now - start) * 1000, 1)
            start = now

        # 1. 쿼리 개선 (선택) - 대화 히스토리 기반
        enhanced = question
        if self.query_enhancer:
            enhanced = self.query_enhancer.enhance(question, history)
            _measure("query_enhance")

        # 2. 전처리 (선택)
        processed = enhanced
        if self.preprocessor:
            processed = self.preprocessor.process(enhanced)
            _measure("preprocess")

        # 3. 임베딩 생성
        embedding = self.embedding_client.embed(processed)
        _measure("embedding")

        # 4. 검색 쿼리 생성
        search_query = self.query_builder.build(
            query=processed,
            embedding=embedding,
            project_id=self.project_id,
            k=self.search_size,
        )
        _measure("query_build")

        # 5. 검색 실행
        results = self._search(search_query)
        _measure("search")

        # 6. 결과 필터링 (선택)
        if self.result_filter:
            results = self.result_filter.filter(processed, results)
            _measure("filter")

        # 7. 청크 확장 (선택)
        if self.chunk_expander:
            results = self.chunk_expander.expand(results)
            _measure("chunk_expand")

        # 8. 컨텍스트 생성
        context = self.context_builder.build(results)
        _measure("context_build")

        # 9. 프롬프트 생성
        system_prompt, user_prompt = self.prompt_template.render(context, question)
        _measure("prompt_render")

        # 10. LLM 호출
        response = self.llm_client.call(user_prompt, system=system_prompt)
        _measure("llm")

        # 전체 소요 시간
        total_ms = sum(timings.values())

        return RAGResult(
            question=question,
            answer=response.content,
            sources=results,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=round(total_ms, 1),
            model=response.model,
            timings=timings,
        )

    def _search(self, query: dict) -> list[dict]:
        """OpenSearch 검색 실행

        search_pipeline이 설정된 경우 파이프라인 파라미터 추가
        """
        if self.search_pipeline:
            # 하이브리드 검색 시 파이프라인 사용
            return self.search_client.search_with_pipeline(
                index=self.index,
                query=query,
                size=self.search_size,
                pipeline=self.search_pipeline,
            )
        else:
            return self.search_client.search(
                index=self.index,
                query=query,
                size=self.search_size,
            )


# =============================================================================
# 팩토리 함수
# =============================================================================


def create_minimal_pipeline(
    project_id: int = 334,
    index: str = "rag-index-fargate-live",
) -> RAGPipeline:
    """최소 구성 파이프라인

    - 전처리: 없음
    - 검색: 순수 벡터 검색 (KNN)
    - 필터: 없음
    - 확장: 없음
    - 컨텍스트: 단순 연결
    - 프롬프트: 단순 RAG

    베이스라인 성능 측정용.
    """
    return RAGPipeline(
        search_client=OpenSearchClient(),
        embedding_client=EmbeddingClient(),
        llm_client=LLMClient(),
        preprocessor=None,
        query_builder=KNNQueryBuilder(),
        result_filter=None,
        chunk_expander=None,
        context_builder=SimpleContextBuilder(),
        prompt_template=SimplePromptTemplate(),
        index=index,
        project_id=project_id,
        search_size=5,
    )


def create_standard_pipeline(
    project_id: int = 334,
    index: str = "rag-index-fargate-live",
) -> RAGPipeline:
    """표준 구성 파이프라인

    - 전처리: 없음 (Nori가 처리)
    - 검색: 하이브리드 (KNN + BM25 with RRF)
    - 필터: Top-K (20 → 5)
    - 확장: 없음
    - 컨텍스트: 메타데이터 포함 + LongContextReorder
    - 프롬프트: 엄격 모드 (할루시네이션 방지)

    운영 권장 구성.
    """
    return RAGPipeline(
        search_client=OpenSearchClient(),
        embedding_client=EmbeddingClient(),
        llm_client=LLMClient(),
        preprocessor=None,
        query_builder=HybridQueryBuilder(),
        result_filter=TopKFilter(k=5),
        chunk_expander=None,
        context_builder=RankedContextBuilder(reorder=True),
        prompt_template=StrictPromptTemplate(),
        index=index,
        project_id=project_id,
        search_size=20,
        search_pipeline=HybridQueryBuilder.SEARCH_PIPELINE,
    )


def create_full_pipeline(
    project_id: int = 334,
    index: str = "rag-index-fargate-live",
) -> RAGPipeline:
    """전체 기능 파이프라인

    - 전처리: 한국어 전처리 (유니코드 정규화, 종결어미 제거)
    - 검색: 하이브리드 (KNN + BM25 with RRF)
    - 필터: Top-K → Reranking (20 → 5)
    - 확장: 이웃 청크 (window=5)
    - 컨텍스트: 메타데이터 포함 + LongContextReorder
    - 프롬프트: 엄격 모드 (할루시네이션 방지)

    최고 품질 구성. 레이턴시가 다소 높음.
    """
    search_client = OpenSearchClient()

    return RAGPipeline(
        search_client=search_client,
        embedding_client=EmbeddingClient(),
        llm_client=LLMClient(),
        preprocessor=KoreanPreprocessor(),
        query_builder=HybridQueryBuilder(),
        result_filter=CompositeFilter(
            [
                TopKFilter(k=20),
                RerankerFilter(top_k=5),
            ]
        ),
        chunk_expander=NeighborChunkExpander(
            opensearch_client=search_client.client,  # raw opensearch client
            index_name=index,
            window=5,
        ),
        context_builder=RankedContextBuilder(reorder=True),
        prompt_template=StrictPromptTemplate(),
        index=index,
        project_id=project_id,
        search_size=50,  # Reranking 전 충분히 가져옴
        search_pipeline=HybridQueryBuilder.SEARCH_PIPELINE,
    )
