# STEP CEA: 청크 확장기 (ChunkExpander)

## 상태: 계획

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

| 위치 | 이웃 조회 대상 | 비용 |
|------|---------------|------|
| CE 전 | 검색 결과 전체 (20개) | 높음 |
| **CE 후** | **Top-K만 (5개)** | **낮음** |

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
              {"term": {"document_id": 123}},
              {"range": {"chunk_index": {"gte": 5, "lte": 15}}}
            ]
          }
        },
        {
          "bool": {
            "filter": [
              {"term": {"document_id": 456}},
              {"range": {"chunk_index": {"gte": 10, "lte": 20}}}
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

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `window` | 5 | 앞뒤 N개 청크 확장 |
| `max_results` | 80 | 최대 반환 결과 수 |

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

## 참고 자료
- [Elasticsearch - Fetch Surrounding Chunks](https://www.elastic.co/search-labs/blog/advanced-chunking-fetch-surrounding-chunks)
- [GraphRAG - Parent-Child Retriever](https://graphrag.com/reference/graphrag/parent-child-retriever/)
- [LanceDB - Parent Document Retriever](https://blog.lancedb.com/modified-rag-parent-document-bigger-chunk-retriever-62b3d1e79bc6)
