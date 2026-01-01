# STEP 6.8: 파이프라인 통합 (RAGPipeline)

## 상태: 완료 ✅

## 목표
모든 단계를 조립하여 E2E 파이프라인 완성

---

## 파이프라인 흐름

```
질문 → 쿼리개선 → 전처리 → 임베딩 → 쿼리생성 → 검색 → 필터링 → 청크확장 → 컨텍스트 → 프롬프트 → LLM → 답변
       (선택)    (선택)                          (선택)   (선택)
```

### 10단계 파이프라인

| 단계 | 컴포넌트 | 설명 |
|------|----------|------|
| 1 | QueryEnhancer | 대화 히스토리 기반 질문 명확화 ("그건 뭐야?" → "연차 휴가 정책은?") |
| 2 | Preprocessor | 질문 전처리 (유니코드 정규화, 종결어미 제거) |
| 3 | EmbeddingClient | 질문 벡터화 (Titan V2) |
| 4 | QueryBuilder | OpenSearch 쿼리 생성 (KNN/Hybrid) |
| 5 | OpenSearchClient | 검색 실행 |
| 6 | ResultFilter | 결과 필터링 (Top-K, Reranking) |
| 7 | ChunkExpander | 이웃 청크 확장 |
| 8 | ContextBuilder | LLM용 컨텍스트 문자열 생성 |
| 9 | PromptTemplate | System/User 프롬프트 생성 |
| 10 | LLMClient | 답변 생성 (Claude) |

---

## 구현

### RAGResult (types.py)

```python
@dataclass
class RAGResult:
    question: str
    answer: str
    sources: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""

    @property
    def source_count(self) -> int:
        return len(self.sources)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
```

### RAGPipeline (pipeline.py)

```python
class RAGPipeline:
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
        query_enhancer: QueryEnhancer | None = None,  # NEW
        result_filter: ResultFilter | None = None,
        chunk_expander: ChunkExpander | None = None,
        # 설정
        index: str = "rag-index-fargate-live",
        project_id: int = 334,
        search_size: int = 20,
        search_pipeline: str | None = None,
    ):
        ...

    def query(
        self,
        question: str,
        history: list[dict] | None = None,  # NEW: 대화 히스토리
    ) -> RAGResult:
        # 10단계 파이프라인 실행
        ...
```

---

## 팩토리 함수 3종

### 1. create_minimal_pipeline (베이스라인)

```python
def create_minimal_pipeline(project_id: int = 334) -> RAGPipeline:
    """최소 구성 - 베이스라인 측정용"""
    return RAGPipeline(
        search_client=OpenSearchClient(),
        embedding_client=EmbeddingClient(),
        llm_client=LLMClient(),
        preprocessor=None,
        query_enhancer=None,
        query_builder=KNNQueryBuilder(),      # 벡터 검색만
        result_filter=None,
        chunk_expander=None,
        context_builder=SimpleContextBuilder(),
        prompt_template=SimplePromptTemplate(),
        search_size=5,
    )
```

### 2. create_standard_pipeline (운영 권장)

```python
def create_standard_pipeline(project_id: int = 334) -> RAGPipeline:
    """표준 구성 - 운영 권장"""
    return RAGPipeline(
        search_client=OpenSearchClient(),
        embedding_client=EmbeddingClient(),
        llm_client=LLMClient(),
        preprocessor=None,                     # Nori가 처리
        query_enhancer=None,                   # 필요시 LLMQueryEnhancer 추가
        query_builder=HybridQueryBuilder(),    # KNN + BM25
        result_filter=TopKFilter(k=5),
        chunk_expander=None,
        context_builder=RankedContextBuilder(reorder=True),
        prompt_template=StrictPromptTemplate(),
        search_size=20,
        search_pipeline="hybrid-rrf",
    )
```

### 3. create_full_pipeline (최고 품질)

```python
def create_full_pipeline(project_id: int = 334) -> RAGPipeline:
    """전체 기능 - 최고 품질, 레이턴시 높음"""
    search_client = OpenSearchClient()
    return RAGPipeline(
        search_client=search_client,
        embedding_client=EmbeddingClient(),
        llm_client=LLMClient(),
        preprocessor=KoreanPreprocessor(),
        query_enhancer=None,  # 필요시 LLMQueryEnhancer(gemini_client) 추가
        query_builder=HybridQueryBuilder(),
        result_filter=CompositeFilter([
            TopKFilter(k=20),
            RerankerFilter(top_k=5),
        ]),
        chunk_expander=NeighborChunkExpander(
            opensearch_client=search_client.client,
            index_name=index,
            window=5,
        ),
        context_builder=RankedContextBuilder(reorder=True),
        prompt_template=StrictPromptTemplate(),
        search_size=50,
        search_pipeline="hybrid-rrf",
    )
```

---

## 사용법

### 기본 사용

```python
from src.rag import create_standard_pipeline

pipeline = create_standard_pipeline(project_id=334)
result = pipeline.query("연차 휴가는 며칠인가요?")

print(result.answer)
print(f"출처: {result.source_count}개")
print(f"토큰: {result.total_tokens}")
print(f"레이턴시: {result.latency_ms:.0f}ms")
```

### 대화 히스토리와 함께 사용 (QueryEnhancer 활용)

```python
from src.rag import RAGPipeline, LLMQueryEnhancer
from src.gemini_client import GeminiClient

# QueryEnhancer가 포함된 파이프라인
pipeline = RAGPipeline(
    ...,
    query_enhancer=LLMQueryEnhancer(GeminiClient()),
)

# 대화 히스토리
history = [
    {"role": "user", "content": "연차 휴가에 대해 알려줘"},
    {"role": "assistant", "content": "연차 휴가는 입사 1년차에 15일이 부여됩니다..."},
]

# "그건" → "연차 휴가"로 자동 변환
result = pipeline.query("그건 어떻게 신청해?", history=history)
```

---

## 파일 구조

```
src/rag/
├── __init__.py          # 모든 컴포넌트 export
├── types.py             # RAGResult 정의
├── pipeline.py          # RAGPipeline + 팩토리 함수
├── preprocessor.py      # 전처리기
├── query_enhancer.py    # 쿼리 개선기 (대화 히스토리 기반)
├── query_builder.py     # 쿼리 빌더
├── result_filter.py     # 결과 필터
├── chunk_expander.py    # 청크 확장기
├── context_builder.py   # 컨텍스트 빌더
└── prompt_template.py   # 프롬프트 템플릿

tests/
└── test_pipeline.py     # 파이프라인 유닛 테스트
```

---

## 테스트

```bash
python -m pytest tests/test_pipeline.py -v
```

### 테스트 커버리지
- [x] RAGResult 기본 필드
- [x] RAGResult 프로퍼티 (source_count, total_tokens)
- [x] 파이프라인 query() 반환값
- [x] 임베딩 클라이언트 호출
- [x] 검색 클라이언트 호출
- [x] LLM 프롬프트 전달
- [x] 전처리기 적용
- [x] 결과 필터 적용
- [x] search_pipeline 파라미터 전달
- [x] create_minimal_pipeline 팩토리

---

## 변경 사항 (계획 대비)

| 항목 | 계획 | 실제 구현 |
|------|------|-----------|
| ResultFilter 시그니처 | `.filter(results)` | `.filter(query, results)` - Reranker에 query 필요 |
| ChunkExpander | 없음 | 추가됨 - 이웃 청크 확장 기능 |
| search_pipeline | 없음 | 추가됨 - 하이브리드 RRF 지원 |
| 팩토리 함수 | 2개 | 3개 - standard 추가 |
| QueryEnhancer | 없음 | 추가됨 - 대화 히스토리 기반 질문 명확화 |
| 파이프라인 단계 | 9단계 | 10단계 - QueryEnhancer 추가 |

---

## 할 일
- [x] RAGResult 데이터 클래스 정의
- [x] RAGPipeline 클래스 구현
- [x] OpenSearchClient에 search_with_pipeline 메서드 추가
- [x] 팩토리 함수 구현 (3종)
- [x] rag/__init__.py 업데이트
- [x] 유닛 테스트 작성 및 통과
- [x] QueryEnhancer 파이프라인 통합
