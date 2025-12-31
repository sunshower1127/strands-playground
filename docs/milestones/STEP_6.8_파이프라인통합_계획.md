# STEP CH: 파이프라인 통합 (RAGPipeline)

## 상태: 계획

## 목표
모든 단계를 조립하여 E2E 파이프라인 완성

---

## 구현

### RAGPipeline 클래스

```python
@dataclass
class RAGResult:
    question: str
    answer: str
    sources: list[dict]  # 검색된 문서들
    input_tokens: int
    output_tokens: int
    latency_ms: float


class RAGPipeline:
    def __init__(
        self,
        # 필수 클라이언트
        search_client: OpenSearchClient,
        embedding_client: EmbeddingClient,
        llm_client: LLMClient,

        # 조립 가능한 컴포넌트
        preprocessor: Preprocessor | None = None,
        query_builder: QueryBuilder,
        result_filter: ResultFilter | None = None,
        context_builder: ContextBuilder,
        prompt_template: PromptTemplate,

        # 설정
        index: str,
        project_id: int,
    ):
        ...

    def query(self, question: str) -> RAGResult:
        start = time.time()

        # 1. 전처리 (선택)
        processed = question
        if self.preprocessor:
            processed = self.preprocessor.process(question)

        # 2. 임베딩 생성
        embedding = self.embedding_client.embed(processed)

        # 3. 검색 쿼리 생성
        search_query = self.query_builder.build(
            query=processed,
            embedding=embedding,
            project_id=self.project_id,
        )

        # 4. 검색 실행
        results = self.search_client.search(self.index, search_query)

        # 5. 결과 필터링 (선택)
        if self.result_filter:
            results = self.result_filter.filter(results)

        # 6. 컨텍스트 생성
        context = self.context_builder.build(results)

        # 7. 프롬프트 생성
        system, user = self.prompt_template.render(context, question)

        # 8. LLM 호출
        response = self.llm_client.call(user, system=system)

        elapsed = (time.time() - start) * 1000

        return RAGResult(
            question=question,
            answer=response.content,
            sources=results,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=elapsed,
        )
```

---

## 팩토리 함수 (편의용)

```python
def create_minimal_pipeline(
    project_id: int = 334,
    index: str = "rag-index-fargate-live",
) -> RAGPipeline:
    """최소 구성 파이프라인"""
    return RAGPipeline(
        search_client=OpenSearchClient(),
        embedding_client=EmbeddingClient(),
        llm_client=LLMClient(),
        preprocessor=None,  # 전처리 없음
        query_builder=KNNQueryBuilder(),  # 벡터 검색만
        result_filter=None,  # 필터 없음
        context_builder=SimpleContextBuilder(),
        prompt_template=SimplePromptTemplate(),
        index=index,
        project_id=project_id,
    )


def create_full_pipeline(
    project_id: int = 334,
    index: str = "rag-index-fargate-live",
) -> RAGPipeline:
    """전체 기능 파이프라인"""
    return RAGPipeline(
        search_client=OpenSearchClient(),
        embedding_client=EmbeddingClient(),
        llm_client=LLMClient(),
        preprocessor=KoreanPreprocessor(),
        query_builder=HybridQueryBuilder(),
        result_filter=AdaptiveThresholdFilter(),
        context_builder=RankedContextBuilder(),
        prompt_template=StrictPromptTemplate(),
        index=index,
        project_id=project_id,
    )
```

---

## E2E 테스트

```python
def test_minimal_pipeline():
    pipeline = create_minimal_pipeline()
    result = pipeline.query("연차 휴가는 며칠인가?")

    assert result.answer  # 답변 존재
    assert len(result.sources) > 0  # 검색 결과 존재
    assert result.latency_ms > 0
```

---

## 파일
- `src/rag/pipeline.py`
- `src/rag/types.py`
- `tests/test_pipeline.py`

---

## 할 일
- [ ] RAGResult 데이터 클래스 정의
- [ ] RAGPipeline 클래스 구현
- [ ] 팩토리 함수 구현
- [ ] E2E 테스트 작성
- [ ] 단일 질문 테스트 통과
