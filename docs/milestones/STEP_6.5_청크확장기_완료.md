# STEP CEA: 청크 확장기 (ChunkExpander)

## 상태: 완료

## 목표

검색 결과의 이웃 청크를 확장하여 컨텍스트 완전성 확보

---

## 배경

### 문제 상황

```
검색 결과: "연차는 15일입니다."  ← 이것만으로는 맥락 부족

실제 문서:
[청크 3] "입사 1년차 직원의 경우..."
[청크 4] "연차는 15일입니다."     ← 검색됨
[청크 5] "2년차부터는 16일로 증가합니다."
```

### 해결 방법

```
검색된 청크 ± N개 이웃 청크 포함 → 완전한 맥락 제공
```

---

## 파이프라인 위치

```
[CD: QueryBuilder]
       ↓
[OpenSearch 검색]
       ↓
[CE: ResultFilter] ← Reranking (Top-K 선별)
       ↓
[CEA: ChunkExpander] ← 여기 (선별된 청크만 확장)
       ↓
[CF: ContextBuilder]
       ↓
[CG: PromptTemplate]
```

### 왜 CE 뒤에 배치?

| 위치      | 이웃 조회 대상        | 비용     |
| --------- | --------------------- | -------- |
| CE 전     | 검색 결과 전체 (20개) | 높음     |
| **CE 후** | **Top-K만 (5개)**     | **낮음** |

→ Top-K만 확장하면 효율적 + 이웃은 대부분 관련 있어서 별도 검증 불필요

---

## 기존 프로젝트 로직 분석

### 설정값

```python
MAX_EXPANDED_RESULTS = 80  # 최대 반환 결과 수
NEIGHBOR_WINDOW = 5        # 이웃 청크 확장 범위 (앞뒤 5개씩)
```

### 기존 방식의 문제점

```python
# 검색 결과마다 개별 쿼리 (N+1 문제)
for result in search_results:
    neighbors = fetch_neighbor_chunks(doc_id, chunk_idx)  # 쿼리 1회
    # 결과 10개면 쿼리 11회 (검색 1 + 이웃 10)
```

---

## 구현할 클래스

### Protocol 정의

```python
class ChunkExpander(Protocol):
    def expand(self, results: list[dict]) -> list[dict]:
        """
        검색 결과에 이웃 청크 추가

        Args:
            results: 검색 결과 리스트 (Rerank 후 Top-K)

        Returns:
            원본 + 이웃 청크가 포함된 확장 리스트
        """
        ...
```

### 1. NoopChunkExpander (베이스라인)

```python
class NoopChunkExpander:
    """확장 안 함 - 원본 그대로 반환"""

    def expand(self, results: list[dict]) -> list[dict]:
        return results
```

### 2. NeighborChunkExpander (권장 - 배치 조회)

```python
class NeighborChunkExpander:
    """이웃 청크 배치 조회로 확장"""

    def __init__(
        self,
        opensearch_client,
        index_name: str,
        window: int = 5,
        max_results: int = 80
    ):
        self.client = opensearch_client
        self.index = index_name
        self.window = window
        self.max_results = max_results

    def expand(self, results: list[dict]) -> list[dict]:
        if not results:
            return results

        # 1. 모든 이웃 조건을 한 번에 수집
        should_clauses = []
        for r in results:
            source = r.get("_source", {})
            doc_id = source.get("document_id")
            chunk_idx = source.get("chunk_index")

            if doc_id is not None and chunk_idx is not None:
                should_clauses.append({
                    "bool": {
                        "filter": [
                            {"term": {"document_id": doc_id}},
                            {"range": {"chunk_index": {
                                "gte": max(0, chunk_idx - self.window),
                                "lte": chunk_idx + self.window
                            }}}
                        ]
                    }
                })

        if not should_clauses:
            return results

        # 2. 한 번의 배치 쿼리로 모든 이웃 조회
        body = {
            "size": self.max_results,
            "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
            "_source": {"excludes": ["embedding"]},
            "sort": [
                {"document_id": "asc"},
                {"chunk_index": "asc"}
            ]
        }

        try:
            response = self.client.search(index=self.index, body=body)
            neighbor_hits = response.get("hits", {}).get("hits", [])
        except Exception as e:
            print(f"⚠️ 이웃 청크 조회 실패: {e}")
            return results

        # 3. 원본 + 이웃 병합 (중복 제거)
        return self._merge_results(results, neighbor_hits)

    def _merge_results(
        self,
        originals: list[dict],
        neighbors: list[dict]
    ) -> list[dict]:
        """원본과 이웃 병합, 중복 제거, 정렬"""
        seen = set()
        merged = []

        # 원본 먼저 추가 (is_neighbor=False)
        for r in originals:
            chunk_id = r.get("_id")
            if chunk_id and chunk_id not in seen:
                r["is_neighbor"] = False
                merged.append(r)
                seen.add(chunk_id)

        # 이웃 추가 (is_neighbor=True)
        for r in neighbors:
            chunk_id = r.get("_id")
            if chunk_id and chunk_id not in seen:
                r["is_neighbor"] = True
                merged.append(r)
                seen.add(chunk_id)

        # 문서별, 청크 순서대로 정렬
        merged.sort(key=lambda x: (
            x.get("_source", {}).get("document_id", 0),
            x.get("_source", {}).get("chunk_index", 0)
        ))

        # 상한 적용
        if len(merged) > self.max_results:
            merged = merged[:self.max_results]

        return merged
```

---

## 배치 조회 vs 개별 조회

### 기존 (개별 조회)

```
검색 1회 + 이웃 조회 N회 = N+1 쿼리
예: 검색 결과 10개 → 11회 쿼리
```

### 개선 (배치 조회)

```
검색 1회 + 이웃 조회 1회 = 2 쿼리
예: 검색 결과 10개 → 2회 쿼리
```

### 배치 쿼리 구조

```json
{
  "query": {
    "bool": {
      "should": [
        {
          "bool": {
            "filter": [
              { "term": { "document_id": 123 } },
              { "range": { "chunk_index": { "gte": 5, "lte": 15 } } }
            ]
          }
        },
        {
          "bool": {
            "filter": [
              { "term": { "document_id": 456 } },
              { "range": { "chunk_index": { "gte": 10, "lte": 20 } } }
            ]
          }
        }
      ],
      "minimum_should_match": 1
    }
  }
}
```

---

## 설정 파라미터

| 파라미터      | 기본값 | 설명               |
| ------------- | ------ | ------------------ |
| `window`      | 5      | 앞뒤 N개 청크 확장 |
| `max_results` | 80     | 최대 반환 결과 수  |

### window 값 선택 가이드

- **3**: 짧은 문서, 빠른 응답 필요시
- **5**: 일반적인 경우 (권장)
- **10**: 긴 문서, 풍부한 맥락 필요시

---

## 출력 형식

```python
[
    {
        "_id": "chunk_123",
        "_source": {
            "document_id": 1,
            "chunk_index": 4,
            "text": "연차는 15일입니다.",
            "file_name": "휴가정책.md",
            ...
        },
        "_score": 0.85,
        "is_neighbor": False  # 원본 검색 결과
    },
    {
        "_id": "chunk_124",
        "_source": {
            "document_id": 1,
            "chunk_index": 5,
            "text": "2년차부터는 16일로 증가합니다.",
            ...
        },
        "_score": None,
        "is_neighbor": True   # 이웃 청크
    },
    ...
]
```

---

## ContextBuilder 연동

```python
# CF: ContextBuilder에서 is_neighbor 활용 가능
class RankedContextBuilder:
    def build(self, results: list[dict]) -> str:
        parts = []
        for i, doc in enumerate(results, 1):
            source = doc["_source"]
            text = source.get("text", "")
            filename = source.get("file_name", "unknown")

            # 이웃 청크 표시 (선택적)
            marker = "[이웃]" if doc.get("is_neighbor") else ""

            parts.append(f"[{i}] ({filename}) {marker}\n{text}")

        return "\n\n".join(parts)
```

---

## 테스트 케이스

### 1. 이웃 확장 기본

```python
expander = NeighborChunkExpander(client, "rag-index", window=2)

results = [
    {"_id": "c1", "_source": {"document_id": 1, "chunk_index": 5, "text": "..."}}
]

expanded = expander.expand(results)
# chunk_index 3, 4, 5, 6, 7 포함 확인
assert len(expanded) >= 1
assert any(r["_source"]["chunk_index"] == 3 for r in expanded)
```

### 2. 중복 제거

```python
# 두 검색 결과가 같은 이웃을 공유할 때
results = [
    {"_id": "c1", "_source": {"document_id": 1, "chunk_index": 5}},
    {"_id": "c2", "_source": {"document_id": 1, "chunk_index": 7}},
]
# chunk_index 6은 둘 다의 이웃 → 한 번만 포함
expanded = expander.expand(results)
chunk_6_count = sum(1 for r in expanded if r["_source"]["chunk_index"] == 6)
assert chunk_6_count == 1
```

### 3. 다른 문서 이웃 분리

```python
results = [
    {"_id": "c1", "_source": {"document_id": 1, "chunk_index": 5}},
    {"_id": "c2", "_source": {"document_id": 2, "chunk_index": 10}},
]
# 각 문서의 이웃은 해당 문서에서만 조회
```

### 4. 빈 결과

```python
expanded = expander.expand([])
assert expanded == []
```

---

## 파일

- `src/rag/chunk_expander.py`
- `tests/test_chunk_expander.py`

---

## 할 일

- [ ] Protocol 정의
- [ ] NoopChunkExpander 구현
- [ ] NeighborChunkExpander 구현 (배치 조회)
- [ ] 테스트 케이스 작성
- [ ] 기존 개별 조회 대비 성능 비교
- [ ] ContextBuilder와 연동 테스트

---

## 향후 개선 방향: 더 세련된 청크 확장

현재 구현은 고정 `window=5`로 단순하지만, 더 발전된 기법들이 존재한다.

### 1. 청크 길이 기반 동적 확장

```
짧은 청크 (100 토큰) → window 10
긴 청크 (500 토큰) → window 2
```

**장점:**

- LLM 호출 없이 휴리스틱으로 결정 가능
- 청크 밀도에 따른 자연스러운 조절

**단점:**

- 청크 길이 ≠ 정보 완결성 (짧아도 완결적일 수 있음)

**효용:** 구현 가치 있음 (저비용으로 적응성 확보)

```python
class AdaptiveChunkExpander:
    def _calculate_window(self, chunk_text: str) -> int:
        """청크 길이에 따른 동적 window 계산"""
        chunk_length = len(chunk_text.split())

        if chunk_length < 50:
            return 8  # 아주 짧은 청크 → 많은 이웃
        elif chunk_length < 150:
            return 5  # 중간
        else:
            return 2  # 긴 청크 → 적은 이웃
```

### 2. LLM이 확장 개수를 사전 결정

질문 복잡도에 따라 LLM이 window 크기를 결정:

- "연차 몇 일?" → window 1-2 (단순 사실)
- "휴가 정책 전체 설명해줘" → window 10+ (포괄적 맥락)

**장점:**

- 질문 복잡도에 따른 적응적 컨텍스트

**단점:**

- LLM 호출 1회 추가 → 레이턴시/비용 증가
- 이미 Reranking 후 Top-K만 확장하므로 추가 LLM 호출 대비 이득이 크지 않음

**효용:** 제한적 (비용 대비 효용 낮음)

### 3. 에이전트에 이웃 청크 조회 Tool 제공 (Agentic RAG)

**가장 최신 트렌드**. LLM이 필요할 때만 추가 컨텍스트를 자율적으로 요청.

```python
# tools/neighbor_chunk_tool.py
class NeighborChunkTool:
    name = "get_neighbor_chunks"
    description = "현재 청크의 앞/뒤 이웃 청크를 조회합니다. 맥락이 부족할 때 사용하세요."

    def run(self, doc_id: str, chunk_idx: int, direction: str = "both", count: int = 3):
        """
        Args:
            doc_id: 문서 ID
            chunk_idx: 현재 청크 인덱스
            direction: "before" | "after" | "both"
            count: 조회할 이웃 개수
        """
        ...
```

**장점:**

- LLM이 **필요할 때만** 추가 컨텍스트 요청
- "이 부분 앞에 뭐가 있지?" → 자율적 판단
- 불필요한 확장 방지

**단점:**

- 에이전트 루프 복잡성 증가
- 여러 번의 Tool call → 레이턴시 증가 가능
- 아직 "demo-grade" (프로덕션 안정성 부족)

**효용:** 높음 (향후 Agentic RAG 전환 시 자연스럽게 도입)

### 4. Contextual Retrieval (Anthropic)

런타임 확장이 아닌 **인덱싱 시점에 사전 컨텍스트 주입**.

```
기존: "연차는 15일입니다."
개선: "[ACME사 휴가정책 문서, 입사 1년차 기준] 연차는 15일입니다."
```

- 각 청크 앞에 50-100 토큰의 맥락 추가
- 검색 실패율 35-67% 감소

**효용:** 매우 높음 (다만 인덱싱 파이프라인 수정 필요)

### 5. TreeRAG / 계층적 청크

```
문서
├── 섹션 요약 (Parent)
│   ├── 세부 청크 1 (Child)
│   ├── 세부 청크 2 (Child)
│   └── ...
```

- Child로 정밀 검색 → Parent로 확장
- "locate precisely first, then expand to read"

### 추천 우선순위

| 순위 | 기법                           | 효용     | 구현 난이도        |
| ---- | ------------------------------ | -------- | ------------------ |
| 1    | **청크 길이 기반 동적 window** | 중       | 낮음 (휴리스틱)    |
| 2    | **Contextual Retrieval**       | 매우높음 | 중간 (인덱싱 수정) |
| 3    | **에이전트 Tool**              | 높음     | 높음 (아키텍처)    |
| 4    | LLM 사전 결정                  | 낮음     | 중간               |

---

## 참고 자료

- [Elasticsearch - Fetch Surrounding Chunks](https://www.elastic.co/search-labs/blog/advanced-chunking-fetch-surrounding-chunks)
- [GraphRAG - Parent-Child Retriever](https://graphrag.com/reference/graphrag/parent-child-retriever/)
- [LanceDB - Parent Document Retriever](https://blog.lancedb.com/modified-rag-parent-document-bigger-chunk-retriever-62b3d1e79bc6)
- [Anthropic - Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [LlamaIndex - RAG is dead, long live agentic retrieval](https://www.llamaindex.ai/blog/rag-is-dead-long-live-agentic-retrieval)
- [RAGFlow - From RAG to Context (2025 Review)](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)
- [IBM - Agentic Chunking with LangChain](https://www.ibm.com/think/tutorials/use-agentic-chunking-to-optimize-llm-inputs-with-langchain-watsonx-ai)
- [Weaviate - What is Agentic RAG](https://weaviate.io/blog/what-is-agentic-rag)
- [Pinecone - Chunking Strategies](https://www.pinecone.io/learn/chunking-strategies/)
- [Firecrawl - Best Chunking Strategies 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025)
