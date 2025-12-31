# 향후 도입 검토 기술

> 각 기술의 상세 내용은 해당 STEP 문서 또는 별도 문서 참조.
>
> **최종 업데이트: 2025-12-31**

---

## 기술별 위치 안내

| 기술 | 상세 문서 | 비고 |
|------|----------|------|
| **HyDE** | [STEP_6.1_쿼리개선기](milestones/STEP_6.1_쿼리개선기_완료.md) | v4 개선 방향 |
| **Query Decomposition** | [STEP_6.1_쿼리개선기](milestones/STEP_6.1_쿼리개선기_완료.md) | v5 개선 방향 |
| **고급 Reranker 옵션** | [STEP_6.4_결과필터](milestones/STEP_6.4_결과필터_계획.md) | 향후 개선 섹션 |
| **Dynamic Chunk Expansion** | [STEP_6.5_청크확장기](milestones/STEP_6.5_청크확장기_계획.md) | 향후 개선 섹션 |
| **Context Formatting** | [STEP_6.6_컨텍스트빌더](milestones/STEP_6.6_컨텍스트빌더_계획.md) | 향후 개선 방향 |
| **Context Compression** | [STEP_6.6_컨텍스트빌더](milestones/STEP_6.6_컨텍스트빌더_계획.md) | 향후 개선 방향 |
| **Hierarchical RAG** | [STEP_6.6_컨텍스트빌더](milestones/STEP_6.6_컨텍스트빌더_계획.md) | 향후 개선 방향 |
| **Parent-Child Retrieval** | [STEP_6.6_컨텍스트빌더](milestones/STEP_6.6_컨텍스트빌더_계획.md) | 향후 개선 방향 |
| **Context Awareness Gate** | [STEP_7_Agent모드](milestones/STEP_7_Agent모드_계획.md) | 향후 개선 섹션 |
| **Dynamic Context Selection** | [STEP_7_Agent모드](milestones/STEP_7_Agent모드_계획.md) | 향후 개선 섹션 |
| **임베딩/인덱싱 개선** | [향후_임베딩_인덱싱_개선.md](향후_임베딩_인덱싱_개선.md) | 별도 문서 |

---

## 우선순위 요약

### 현재 계획 (구현 예정)
| 기술 | 복잡도 | 효과 | 위치 |
|------|--------|------|------|
| **LongContextReorder** | 낮음 | 중간 | STEP_6.6 |
| **HybridSearch (RRF)** | 낮음 | 높음 | STEP_6.3 |
| **FlashRank Reranker** | 낮음 | 중-상 | STEP_6.4 |

### 1차 개선 후보
| 기술 | 복잡도 | 효과 | 도입 시점 |
|------|--------|------|----------|
| **BGE-reranker-v2-m3** | 낮음 | 상 | FlashRank 품질 이슈시 |
| **Query Decomposition** | 중간 | 높음 | 비교 질문 대응 필요시 |
| **HyDE** | 중간 | 중-상 | 검색 품질 이슈시 |

### 2차 개선 후보 (비용/복잡도 높음)
| 기술 | 복잡도 | 효과 | 도입 시점 |
|------|--------|------|----------|
| **Context Compression** | 높음 | 높음 | 토큰 비용 문제시 |
| **Voyage AI Embedding** | 낮음 | 높음 | Titan 대체 필요시 |
| **Late Chunking** | 중간 | 중-상 | 인덱싱 개선시 |
| **Contextual Retrieval** | 높음 | 높음 | 비용 허용시 |

---

## 참고 문헌

### RAG 일반
1. [A Survey of Context Engineering for LLMs (2025)](https://arxiv.org/abs/2507.13334)
2. [Lost in the Middle (Stanford, 2024)](https://arxiv.org/abs/2307.03172)
3. [VectorHub - Optimizing RAG](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking)

### Reranking
4. [Pinecone - Rerankers](https://www.pinecone.io/learn/series/rag/rerankers/)
5. [ZeroEntropy - Best Reranking Model 2025](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025)

### Query Transformation
6. [HyDE Paper (arXiv 2022)](https://arxiv.org/abs/2212.10496)
7. [Haystack - Query Decomposition](https://haystack.deepset.ai/cookbook/query_decomposition)
8. [HopRAG Paper (2025)](https://arxiv.org/html/2502.12442v1)

### Chunking & Embeddings
9. [Best Chunking Strategies 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025)
10. [Jina AI - Late Chunking](https://jina.ai/news/late-chunking-in-long-context-embedding-models/)
11. [Voyage AI - voyage-3.5](https://blog.voyageai.com/2025/05/20/voyage-3-5/)

### Anthropic
12. [Anthropic - Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
13. [Anthropic - Prompt Caching](https://www.anthropic.com/news/prompt-caching)

### 기타
14. [Context Compression Survey (2024)](https://arxiv.org/html/2409.13385v1)
15. [Context Awareness Gate (2024)](https://arxiv.org/html/2411.16133)
16. [Dynamic Context Selection (2024)](https://arxiv.org/html/2512.14313)
