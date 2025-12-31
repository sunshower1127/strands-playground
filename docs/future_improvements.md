# 향후 도입 검토 기술

> 현재는 과하지만, 프로젝트가 성숙하면 도입을 고려할 만한 기술들
>
> **최종 업데이트: 2025-12-31** (2025년 최신 연구 반영)

---

## 우선순위 요약

| 기술 | 복잡도 | 효과 | 우선순위 | 비고 |
|------|--------|------|----------|------|
| **LongContextReorder** | 낮음 | 중간 | ✅ 현재 계획 | Lost in the Middle 대응 |
| **HybridSearch (RRF)** | 낮음 | 높음 | ✅ 현재 계획 | BM25 + KNN |
| **FlashRank Reranker** | 낮음 | 중-상 | ✅ 현재 계획 | CPU 최적화 |
| **BGE-reranker-v2-m3** | 낮음 | 상 | 🔄 FlashRank 대체 검토 | 더 정확, 무료 |
| **HyDE** | 중간 | 중-상 | ⏳ 검색 품질 이슈 시 | 가상 문서 임베딩 |
| **Query Decomposition** | 중간 | 높음 | ⏳ 복잡 질문 대응 시 | 다단계 질문 분해 |
| **Late Chunking** | 중간 | 중-상 | ⏳ 인덱싱 개선 시 | 문맥 보존 청킹 |
| **Contextual Retrieval** | 높음 | 높음 | ⏳ 비용 허용 시 | Anthropic 방식 |
| **Voyage AI Embedding** | 낮음 | 높음 | 🔄 Titan 대체 검토 | SOTA 임베딩 |
| **Semantic Chunking** | 중간 | 중-상 | ⏳ 청킹 개선 시 | 의미 단위 분할 |
| **Context Compression** | 높음 | 높음 | ⏳ 토큰 비용 문제시 | LLM 2회 호출 |
| **ColBERT v2** | 높음 | 높음 | ⏳ 대규모 검색 시 | Late Interaction |

---

## 1. HyDE (Hypothetical Document Embeddings) ⭐ 신규

### 개요
질문을 가상의 답변 문서로 변환 후 검색하는 기법.

```
[일반 RAG]
질문("연차 몇일?") ──► 임베딩 ──► 검색 ──► 답변

[HyDE]
질문 ──► LLM(가상 답변 생성) ──► 가상 답변 임베딩 ──► 검색 ──► 답변
```

### 왜 효과적인가?
- 짧은 질문 ↔ 긴 문서 간 **semantic gap 해소**
- 질문 형태 vs 답변 형태의 임베딩 분포가 다름
- 가상 답변은 실제 문서와 임베딩 공간에서 더 가까움

### 성능
- Zero-shot으로 **10-12% 검색 정확도 향상**
- 한국어/일본어 등 비영어권에서도 효과적
- BM25, Contriever 대비 일관된 성능 향상

### 구현 예시
```python
# LlamaIndex
from llama_index.core.indices.query.query_transform.base import HyDEQueryTransform

hyde = HyDEQueryTransform(include_original=True)
query_engine = TransformQueryEngine(base_engine, query_transform=hyde)

# LangChain
from langchain.chains import HypotheticalDocumentEmbedder

hyde_embedder = HypotheticalDocumentEmbedder.from_llm(
    llm=llm,
    base_embeddings=embeddings,
    prompt_key="web_search"  # 또는 custom prompt
)
```

### 단점
- LLM 1회 추가 호출 → 레이턴시 증가
- 가상 답변이 잘못된 방향으로 생성될 수 있음

### 도입 시점
- 검색 품질이 기대에 미치지 못할 때
- 질문이 추상적이거나 복잡할 때

### 참고 자료
- [HyDE 원 논문 (arXiv 2022)](https://arxiv.org/abs/2212.10496)
- [Zilliz - Improve RAG with HyDE](https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings)

---

## 2. Query Decomposition (질문 분해) ⭐ 신규

### 개요
복잡한 질문을 단순한 하위 질문들로 분해 후 각각 검색.

```
원본 질문: "A사와 B사의 연차 정책 차이점은?"
      ↓ 분해
["A사의 연차 정책은?", "B사의 연차 정책은?"]
      ↓ 각각 검색
[A사 문서들, B사 문서들]
      ↓ 통합 + Rerank
최종 컨텍스트
```

### 2025 연구 결과
| 프레임워크 | 성능 향상 | 특징 |
|-----------|----------|------|
| [Question Decomposition RAG](https://aclanthology.org/2025.acl-srw.32.pdf) | MRR@10 +36.7%, F1 +11.6% | 분해 → 검색 → Rerank |
| [HopRAG](https://arxiv.org/html/2502.12442v1) | 답변 정확도 +76.78% | 그래프 기반 다단계 추론 |
| [MQRF-RAG](https://dl.acm.org/doi/10.1145/3728199.3728221) | HotPotQA +7% | 4가지 쿼리 스타일 생성 |

### 구현 예시
```python
# LlamaIndex Multi-Step Query
from llama_index.core.query_engine import MultiStepQueryEngine
from llama_index.core.indices.query.query_transform import StepDecomposeQueryTransform

step_decompose = StepDecomposeQueryTransform(llm=llm, verbose=True)
query_engine = MultiStepQueryEngine(
    query_engine=base_engine,
    query_transform=step_decompose,
    num_steps=3
)
```

### 도입 시점
- 비교 질문이 많을 때 ("A와 B의 차이", "X vs Y")
- 다단계 추론이 필요한 질문
- 단일 검색으로 답변 품질이 낮을 때

### 참고 자료
- [Haystack - Query Decomposition Cookbook](https://haystack.deepset.ai/cookbook/query_decomposition)
- [MultiHop-RAG Benchmark](https://openreview.net/forum?id=t4eB3zYWBK)

---

## 3. Late Chunking (후기 청킹) ⭐ 신규

### 개요
청킹 후 임베딩이 아닌, 임베딩 후 청킹으로 문맥 보존.

```
[기존 방식]
문서 ──► 청크 분할 ──► 각 청크 개별 임베딩 (문맥 손실!)

[Late Chunking]
문서 ──► 전체 토큰 임베딩 ──► 토큰 임베딩을 청크로 분할 ──► Mean Pooling
```

### 왜 효과적인가?
- "그는", "이 회사" 같은 대명사 참조 문맥 보존
- 전체 문서의 attention 정보가 각 청크에 반영됨

### 성능
- 대명사 참조 문서에서 **10-12% 검색 정확도 향상**
- 추가 학습 없이 적용 가능
- Contextual Retrieval 대비 **비용 효율적**

### vs Contextual Retrieval
| 방식 | 비용 | 정확도 | 구현 복잡도 |
|------|------|--------|------------|
| Late Chunking | 낮음 (임베딩만) | 중-상 | 중간 |
| Contextual Retrieval | 높음 (LLM 호출) | 상 | 높음 |

### 제약 사항
- Long-context 임베딩 모델 필요 (jina-embeddings-v2 등)
- 인덱싱 시점에 적용 (쿼리 시점 아님)

### 참고 자료
- [Jina AI - Late Chunking](https://jina.ai/news/late-chunking-in-long-context-embedding-models/)
- [Weaviate - Late Chunking](https://weaviate.io/blog/late-chunking)
- [Late Chunking Paper (arXiv)](https://arxiv.org/abs/2409.04701)
- [GitHub - jina-ai/late-chunking](https://github.com/jina-ai/late-chunking)

---

## 4. Anthropic Contextual Retrieval ⭐ 신규

### 개요
각 청크에 LLM으로 문맥 정보를 추가하는 Anthropic의 방식.

```
원본 청크: "그는 2024년 CEO가 되었다"
      ↓ LLM 문맥 추가
보강된 청크: "[이 문서는 삼성전자 이재용 회장에 대한 것입니다] 그는 2024년 CEO가 되었다"
```

### 성능 (Anthropic 공식)
- 검색 실패율 **49% 감소**
- Reranking 결합 시 **67% 감소**

### 비용 최적화: Prompt Caching
```
일반 방식: 청크마다 전체 문서 전달 → 비용 폭발

Prompt Caching 활용:
1. 전체 문서를 캐시에 한 번 로드
2. 각 청크 처리 시 캐시된 문서 참조
→ 비용 90% 절감, 레이턴시 85% 감소 (11.5s → 2.4s)
```

**예상 비용**: 청크당 약 $1.02/M 토큰 (800토큰 청크, 8K 문서 기준)

### 도입 시점
- 검색 품질이 매우 중요할 때
- 토큰 비용을 감당할 수 있을 때
- 대명사/참조가 많은 문서

### 참고 자료
- [Anthropic - Contextual Retrieval 발표](https://www.anthropic.com/news/contextual-retrieval)
- [Anthropic Engineering - Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Anthropic - Prompt Caching](https://www.anthropic.com/news/prompt-caching)

---

## 5. 고급 Reranker 옵션 ⭐ 신규

### 2025 Reranker 비교

| 모델 | 정확도 | 속도 | 비용 | 다국어 | 특징 |
|------|--------|------|------|--------|------|
| **FlashRank** | Good | Very Fast | Free | 제한적 | ONNX, CPU 최적화 |
| **BGE-reranker-v2-m3** | High | Moderate | Free | ✅ | 오픈소스 SOTA |
| **Cohere Rerank 3.5** | High | Fast | API | ✅ 100+ | 프로덕션 안정성 |
| **Cohere Rerank 3.5 Nimble** | High | Very Fast | API | ✅ | 속도 최적화 버전 |
| **Voyage Rerank 2.5** | Very High | Fast | API | ✅ | 최신 SOTA |

### rerankers 라이브러리 활용
```python
from rerankers import Reranker

# FlashRank (현재 계획)
ranker = Reranker("ms-marco-MiniLM-L-12-v2", model_type="flashrank")

# BGE (더 정확, 무료) - 추천
ranker = Reranker("BAAI/bge-reranker-v2-m3", model_type="cross-encoder")

# Cohere (API, 프로덕션)
ranker = Reranker("rerank-english-v3.0", model_type="cohere")

# 사용
results = ranker.rank(query="질문", docs=["문서1", "문서2", ...])
```

### 권장 전략
1. **시작**: FlashRank (빠르고 무료)
2. **품질 개선 필요시**: BGE-reranker-v2-m3
3. **프로덕션 + 다국어**: Cohere Rerank 3.5

### 참고 자료
- [ZeroEntropy - Best Reranking Model 2025](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025)
- [Agentset Reranker Leaderboard](https://agentset.ai/rerankers)
- [AnswerDotAI/rerankers GitHub](https://github.com/AnswerDotAI/rerankers)

---

## 6. ColBERT v2 / Late Interaction Models ⭐ 신규

### 개요
Cross-Encoder 수준 정확도 + Bi-Encoder 수준 속도를 제공하는 모델.

```
[Bi-Encoder]
Query ──► 임베딩 ──┐
                  ├──► 코사인 유사도 (빠름, 덜 정확)
Doc ──► 임베딩 ───┘

[Cross-Encoder]
(Query, Doc) ──► 함께 인코딩 ──► 점수 (느림, 정확)

[ColBERT - Late Interaction]
Query ──► 토큰별 임베딩 ──┐
                         ├──► MaxSim (빠름 + 정확)
Doc ──► 토큰별 임베딩 ────┘
```

### ColBERTv2 특징
- 공간 효율: 기존 대비 **6-10배 절감** (Residual Compression)
- [PLAID Engine](https://dl.acm.org/doi/10.1145/3511808.3557325): GPU에서 7배, CPU에서 45배 빠름
- 140M 패시지에서도 수십~수백 ms 레이턴시

### Jina-ColBERT-v2 (2024)
- **다국어 지원** 포함
- ColBERTv2 대비 개선된 학습 파이프라인

### 도입 시점
- 대규모 검색 + 높은 정확도가 모두 필요할 때
- Cross-Encoder가 너무 느릴 때

### 참고 자료
- [ColBERTv2 Paper](https://arxiv.org/abs/2112.01488)
- [Jina-ColBERT-v2 Paper](https://arxiv.org/abs/2408.16672)
- [Weaviate - Late Interaction Overview](https://weaviate.io/blog/late-interaction-overview)
- [Stanford ColBERT GitHub](https://github.com/stanford-futuredata/ColBERT)

---

## 7. Voyage AI Embeddings ⭐ 신규

### 2025 임베딩 모델 비교

| 모델 | vs OpenAI text-embedding-3-large | 차원 | 컨텍스트 | 비용 |
|------|----------------------------------|------|----------|------|
| **voyage-3-large** | **+9.74%** | 1024-2048 | 32K | 비슷 |
| **voyage-3.5** | **+8.26%** | 2048 | 32K | 2.2배 저렴 |
| **voyage-3.5-lite** | **+6.34%** | 2048 | 32K | 6.5배 저렴 |
| OpenAI text-embedding-3-large | 기준 | 3072 | 8K | 기준 |
| Amazon Titan | - | 1024 | 8K | 저렴 |

### Voyage AI 장점
- **32K 토큰 컨텍스트** (OpenAI 8K의 4배)
- **Matryoshka 임베딩**: 차원 조절 가능 (2048 → 256)
- **다국어 성능 우수** (한국어 포함)
- int8/binary 양자화로 **벡터DB 비용 83% 절감**

### 도입 시점
- Amazon Titan보다 높은 정확도 필요 시
- 긴 문서 임베딩이 필요할 때

### 참고 자료
- [Voyage AI - voyage-3-large 발표](https://blog.voyageai.com/2025/01/07/voyage-3-large/)
- [Voyage AI - voyage-3.5 발표](https://blog.voyageai.com/2025/05/20/voyage-3-5/)
- [Best Embedding Models 2025](https://elephas.app/blog/best-embedding-models)

---

## 8. Semantic Chunking (의미 기반 청킹) ⭐ 신규

### 개요
고정 크기가 아닌 의미 단위로 문서 분할.

```
[Fixed-size Chunking]
문서 ──► 500토큰씩 자르기 (문장 중간에 끊길 수 있음)

[Semantic Chunking]
문서 ──► 문장 임베딩 ──► 유사도 급변 지점에서 분할
```

### 성능 (2025 연구)
- 고정 크기 대비 **15-30% 검색 정확도 향상**
- [Max-Min Semantic Chunking](https://link.springer.com/article/10.1007/s10791-025-09638-7): 의미적 일관성 보존

### 단점
- 청킹 시 임베딩 비용 발생
- 구현 복잡도 증가

### 현실적 대안
```python
# RecursiveCharacterTextSplitter가 좋은 기본값
# 400-512 토큰, 10-20% 오버랩 → 85-90% recall
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ".", " "]
)
```

### 참고 자료
- [Firecrawl - Best Chunking Strategies 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025)
- [Weaviate - Chunking Strategies](https://weaviate.io/blog/chunking-strategies-for-rag)

---

## 9. Context Compression (컨텍스트 압축)

### 개요
검색 결과를 LLM에 바로 전달하지 않고, 먼저 압축/요약 후 전달.

```
[일반 RAG]
검색결과(10K 토큰) ────────────────────► LLM ──► 답변

[Context Compression]
검색결과(10K 토큰) ──► LLM(압축) ──► 압축본(2K) ──► LLM ──► 답변
```

### 장점
- 토큰 비용 절감 (특히 GPT-4 같은 고가 모델)
- 긴 컨텍스트의 노이즈 제거
- "Lost in the Middle" 문제 완화

### 단점
- LLM 2번 호출 (레이턴시 증가)
- 압축 과정에서 정보 손실 가능
- 구현 복잡도 증가

### 도입 시점
- 컨텍스트가 consistently 10K+ 토큰일 때
- 토큰 비용이 병목일 때
- 답변 품질이 긴 컨텍스트로 인해 저하될 때

### 참고 자료
- [Contextual Compression in RAG Survey (arXiv)](https://arxiv.org/html/2409.13385v1)
- LangChain `ContextualCompressionRetriever`

---

## 10. Dynamic Context Selection (동적 컨텍스트 선택)

### 개요
쿼리 특성에 따라 검색 결과 개수(k)나 포맷을 동적으로 결정.

```python
# 예시: 쿼리 복잡도에 따른 k값 조절
def select_k(query: str) -> int:
    complexity = classify_query(query)  # LLM 또는 classifier
    if complexity == "simple":
        return 3
    elif complexity == "complex":
        return 10
    return 5
```

### 2025 연구: DynamicRAG
[DynamicRAG Paper](https://medium.com/@sindhuja.codes/when-to-rerank-and-when-to-let-semantic-search-do-its-job-af3adddd602b)
- 고정 k 대신 **동적으로 문서 수 결정**
- Reranking 필요 여부도 동적 판단

### 현실적 대안 (지금 쓸 수 있음)
```python
def select_k_simple(query: str) -> int:
    # Rule-based: LLM 호출 없이
    if "비교" in query or "차이" in query:
        return 7  # 비교 질문은 더 많이
    if len(query) < 20:
        return 3  # 짧은 질문은 적게
    return 5
```

### 참고 자료
- [Dynamic Context Selection for RAG (arXiv)](https://arxiv.org/html/2512.14313)
- [Adaptive-RAG Framework](https://arxiv.org/html/2506.00054v1)

---

## 11. Context Awareness Gate (CAG)

### 개요
"이 질문에 외부 컨텍스트가 필요한가?"를 먼저 판단.

```
질문 ──► CAG 판단 ──┬── 필요함 ──► RAG 파이프라인 ──► 답변
                   │
                   └── 불필요 ──► LLM 직접 답변
```

### 장점
- LLM 기본 지식으로 충분한 질문은 검색 생략
- 레이턴시 및 비용 절감

### 단점
- 판단 오류 시 hallucination 위험
- 기업 내부 문서 RAG에서는 대부분 검색 필요

### 도입 시점
- 일반 지식 질문과 도메인 질문이 혼재할 때
- 검색이 불필요한 질문이 상당수일 때

### 참고 자료
- [Context Awareness Gate for RAG (arXiv)](https://arxiv.org/html/2411.16133)

---

## 12. Hierarchical RAG (계층적 검색)

### 개요
문서 → 섹션 → 단락 순으로 계층적 검색.

```
1. 후보 문서 검색 (top 20)
      ↓
2. 문서 내 관련 섹션 검색 (top 10)
      ↓
3. 섹션 내 관련 단락 검색 (top 5)
      ↓
4. 최종 단락만 LLM에 전달
```

### 장점
- 대규모 문서에서 정밀한 검색
- "Lost in the Middle" 완화
- 컨텍스트 품질 향상

### 단점
- 인덱싱 복잡도 증가
- 검색 단계 증가로 레이턴시 증가

### 도입 시점
- 문서가 매우 길고 구조화되어 있을 때
- 단일 검색으로 정확도가 부족할 때

---

## 13. Parent-Child Retrieval (Sentence Window)

### 개요
작은 청크로 검색하고, 큰 청크로 컨텍스트 제공.

```
인덱싱:
- Parent 청크: 2000 토큰 (LLM 컨텍스트용)
- Child 청크: 200 토큰 (검색용)

검색:
Child로 검색 ──► Parent 청크 반환 ──► LLM
(정밀 검색)      (충분한 문맥)
```

### 장점
- 검색 정밀도 + 컨텍스트 완전성 모두 확보
- 구현 상대적으로 간단

### 참고 자료
- [LlamaIndex - Sentence Window Retrieval](https://docs.llamaindex.ai/en/stable/examples/node_postprocessor/MetadataReplacementDemo/)

---

## 14. Query-Aware Context Formatting (쿼리 인식 포맷팅)

### 개요
질문 유형에 따라 컨텍스트 포맷을 다르게 구성.

| 질문 유형 | 추천 포맷 |
|----------|----------|
| 사실 확인 | 간단한 번호 목록 |
| 비교 질문 | 테이블 형태 |
| 분석 질문 | 상세 메타데이터 포함 |

### 연구 결과
[arXiv 2411.10541](https://arxiv.org/html/2411.10541v1)에 따르면:
- GPT-3.5: 포맷에 따라 **최대 40% 성능 차이**
- GPT-4: 상대적으로 안정적
- **최적 포맷이 모델/태스크마다 다름**

### 현실적 접근
LLM에게 포맷 결정을 맡기는 것보다, A/B 테스트로 최적 포맷을 찾아 고정하는 것이 효율적.

---

## 현재 적용 기술

### LongContextReorder (Lost in the Middle 대응)

```python
def reorder_for_attention(results: list[dict]) -> list[dict]:
    """
    U-shaped attention 패턴 활용
    - 가장 관련도 높은 문서: 처음과 끝에 배치
    - 관련도 낮은 문서: 중간에 배치
    """
    reordered = []
    for i, doc in enumerate(results):
        if i % 2 == 0:
            reordered.insert(len(reordered) // 2, doc)
        else:
            reordered.append(doc)
    return reordered
```

**근거**: [Lost in the Middle (Stanford, 2024)](https://arxiv.org/abs/2307.03172)
- 중간 위치 정보 무시 → 최대 30% 성능 저하
- Reorder로 유의미한 성능 회복

---

## 참고 문헌

### RAG 일반
1. [A Survey of Context Engineering for LLMs (2025)](https://arxiv.org/abs/2507.13334)
2. [Lost in the Middle: How Language Models Use Long Contexts (2024)](https://arxiv.org/abs/2307.03172)
3. [VectorHub - Optimizing RAG with Hybrid Search & Reranking](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking)
4. [Advanced RAG Techniques - Neo4j](https://neo4j.com/blog/genai/advanced-rag-techniques/)

### Reranking
5. [Pinecone - Rerankers](https://www.pinecone.io/learn/series/rag/rerankers/)
6. [ZeroEntropy - Best Reranking Model 2025](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025)
7. [Agentset Reranker Leaderboard](https://agentset.ai/rerankers)

### Chunking
8. [Best Chunking Strategies for RAG 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025)
9. [Weaviate - Chunking Strategies](https://weaviate.io/blog/chunking-strategies-for-rag)
10. [Jina AI - Late Chunking](https://jina.ai/news/late-chunking-in-long-context-embedding-models/)

### Query Transformation
11. [HyDE Paper (arXiv 2022)](https://arxiv.org/abs/2212.10496)
12. [Haystack - Query Decomposition](https://haystack.deepset.ai/cookbook/query_decomposition)
13. [HopRAG Paper (2025)](https://arxiv.org/html/2502.12442v1)

### Embeddings
14. [Voyage AI - voyage-3-large](https://blog.voyageai.com/2025/01/07/voyage-3-large/)
15. [Voyage AI - voyage-3.5](https://blog.voyageai.com/2025/05/20/voyage-3-5/)
16. [Best Embedding Models 2025](https://elephas.app/blog/best-embedding-models)

### Anthropic
17. [Anthropic - Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
18. [Anthropic - Prompt Caching](https://www.anthropic.com/news/prompt-caching)

### Late Interaction
19. [ColBERTv2 Paper](https://arxiv.org/abs/2112.01488)
20. [Jina-ColBERT-v2 Paper](https://arxiv.org/abs/2408.16672)
21. [Weaviate - Late Interaction Overview](https://weaviate.io/blog/late-interaction-overview)

### 기타
22. [Does Prompt Formatting Have Any Impact on LLM Performance? (2024)](https://arxiv.org/abs/2411.10541)
23. [Contextual Compression in RAG Survey (2024)](https://arxiv.org/html/2409.13385v1)
24. [Context Awareness Gate for RAG (2024)](https://arxiv.org/html/2411.16133)
25. [Dynamic Context Selection for RAG (2024)](https://arxiv.org/html/2512.14313)
