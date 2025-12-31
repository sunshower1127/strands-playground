# STEP CF: 컨텍스트 빌더 (ContextBuilder)

## 상태: 완료

## 목표

검색 결과 → LLM에 주입할 컨텍스트 문자열 생성

---

## 조사 결과 요약

### OpenSearch 내장 RAG 프로세서

OpenSearch 2.12+에서 `retrieval_augmented_generation` 프로세서 제공.

- 검색 → 컨텍스트 → LLM 호출이 파이프라인 하나로 처리됨
- **하지만** 커스텀 포맷팅 제한적 → 직접 구현이 더 유연

### 최적 파라미터 (연구 기반)

| 항목               | 권장값                   | 근거                          |
| ------------------ | ------------------------ | ----------------------------- |
| 검색 결과 개수 (k) | 5-7개                    | 10개 이상시 성능 저하 (arXiv) |
| 청크 크기          | 512 토큰                 | NVIDIA 2024 연구              |
| 컨텍스트 총량      | 컨텍스트 윈도우의 30-40% | 50% 초과시 성능 저하          |

### Lost in the Middle 문제 (중요!)

[Stanford 연구](https://arxiv.org/abs/2307.03172): LLM은 컨텍스트 **처음과 끝**은 잘 활용하지만 **중간은 무시**하는 경향.

- 성능 저하: 최대 30%
- **해결책**: LongContextReorder 적용

---

## 구현할 클래스

### Protocol 정의

```python
class ContextBuilder(Protocol):
    def build(self, results: list[dict]) -> str: ...
```

### 1. SimpleContextBuilder (베이스라인)

단순 연결:

```python
def build(self, results: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(results, 1):
        text = doc["_source"].get("text", "")
        parts.append(f"[{i}]\n{text}")
    return "\n\n".join(parts)
```

출력 예시:

```
[1]
연차 휴가는 입사 1년차 15일, 2년차부터 16일이 부여됩니다...

[2]
경조사 휴가는 결혼 5일, 출산 10일이 제공됩니다...
```

### 2. RankedContextBuilder (권장)

메타데이터 + LongContextReorder 적용:

```python
class RankedContextBuilder:
    def __init__(self, reorder: bool = True, include_score: bool = False):
        self.reorder = reorder
        self.include_score = include_score

    def _reorder_for_attention(self, results: list[dict]) -> list[dict]:
        """
        U-shaped attention 패턴 활용
        - 관련도 높은 문서: 처음과 끝에 배치
        - 관련도 낮은 문서: 중간에 배치
        """
        if not self.reorder:
            return results

        reordered = []
        for i, doc in enumerate(results):
            if i % 2 == 0:
                reordered.insert(len(reordered) // 2, doc)
            else:
                reordered.append(doc)
        return reordered

    def build(self, results: list[dict]) -> str:
        reordered = self._reorder_for_attention(results)

        parts = []
        for i, doc in enumerate(reordered, 1):
            source = doc["_source"]
            text = source.get("text", "")
            filename = source.get("file_name", "unknown")
            page = source.get("page_number", "?")

            header = f"[{i}] ({filename}, p.{page})"
            if self.include_score and "_score" in doc:
                header += f" [score: {doc['_score']:.3f}]"

            parts.append(f"{header}\n{text}")

        return "\n\n".join(parts)
```

출력 예시:

```
[1] (휴가정책.md, p.2)
연차 휴가는 입사 1년차 15일, 2년차부터 16일이 부여됩니다...

[2] (복지제도.md, p.5)
경조사 휴가는 결혼 5일, 출산 10일이 제공됩니다...
```

### 3. DebugContextBuilder

점수 포함 (디버깅용):

```
[1] (휴가정책.md, p.2) [score: 0.85]
...
```

→ `RankedContextBuilder(include_score=True)`로 대체 가능

---

## 설계 결정

### ContextBuilder vs PromptTemplate 분리 이유

```
검색결과 ──► ContextBuilder ──► context(str) ──► PromptTemplate ──► LLM
            "문서 포맷팅"                        "LLM 지시사항"
```

분리의 장점:

1. **디버깅** - context만 따로 출력해서 확인 가능
2. **A/B 테스트** - 같은 context로 다른 프롬프트 비교
3. **단일 책임** - 각 클래스가 하나의 역할만

### 검토했으나 보류한 기술

| 기술                   | 이유                             |
| ---------------------- | -------------------------------- |
| Context Compression    | LLM 2번 호출, 현재 규모에서 과함 |
| 동적 포맷 선택         | LLM 2번 호출, 효과 불확실        |
| Query-Aware Formatting | Rule-based로 충분                |

→ 상세 내용: [future_improvements.md](../future_improvements.md)

---

## 고려사항

### 텍스트 길이 제한

- LLM 컨텍스트 윈도우의 30-40% 이하 권장
- 너무 긴 경우: k값 조절 또는 truncate
- 50% 초과시 성능 저하 연구 결과 있음

### 필드 선택

OpenSearch 인덱스에서 사용 가능한 필드:

- `text`: 본문
- `chunk_text`: 청크 텍스트
- `file_name`: 파일명
- `page_number`: 페이지 번호
- `original_filename`: 원본 파일명

→ 실제 인덱스 확인 후 결정

---

## 파일

- `src/rag/context_builder.py`
- `tests/test_context_builder.py`

---

## 할 일

- [ ] Protocol 정의
- [ ] SimpleContextBuilder 구현
- [ ] RankedContextBuilder 구현 (LongContextReorder 포함)
- [ ] 실제 검색 결과로 출력 확인
- [ ] reorder on/off 성능 비교 (가능하면)

---

## 참고 자료

- [Lost in the Middle (Stanford, 2024)](https://arxiv.org/abs/2307.03172)
- [Context Window Utilization (arXiv)](https://arxiv.org/html/2407.19794v2)
- [Best Chunking Strategies 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025)
- [OpenSearch RAG Processor](https://docs.opensearch.org/latest/search-plugins/search-pipelines/rag-processor/)

---

## 향후 개선 방향

### 1. Query-Aware Context Formatting (쿼리 인식 포맷팅)

질문 유형에 따라 컨텍스트 포맷을 다르게 구성.

| 질문 유형 | 추천 포맷            |
| --------- | -------------------- |
| 사실 확인 | 간단한 번호 목록     |
| 비교 질문 | 테이블 형태          |
| 분석 질문 | 상세 메타데이터 포함 |

**연구 결과** ([arXiv 2411.10541](https://arxiv.org/html/2411.10541v1)):

- GPT-3.5: 포맷에 따라 **최대 40% 성능 차이**
- GPT-4: 상대적으로 안정적
- **최적 포맷이 모델/태스크마다 다름**

**현실적 접근**: LLM에게 포맷 결정을 맡기는 것보다, A/B 테스트로 최적 포맷을 찾아 고정하는 것이 효율적.

### 2. Context Compression (컨텍스트 압축)

검색 결과를 LLM에 바로 전달하지 않고, 먼저 압축/요약 후 전달.

```
[일반 RAG]
검색결과(10K 토큰) ────────────────────► LLM ──► 답변

[Context Compression]
검색결과(10K 토큰) ──► LLM(압축) ──► 압축본(2K) ──► LLM ──► 답변
```

**장점:**

- 토큰 비용 절감 (특히 GPT-4 같은 고가 모델)
- 긴 컨텍스트의 노이즈 제거
- "Lost in the Middle" 문제 완화

**단점:**

- LLM 2번 호출 (레이턴시 증가)
- 압축 과정에서 정보 손실 가능

**도입 시점:**

- 컨텍스트가 consistently 10K+ 토큰일 때
- 토큰 비용이 병목일 때

**참고:**

- [Contextual Compression in RAG Survey (arXiv)](https://arxiv.org/html/2409.13385v1)
- LangChain `ContextualCompressionRetriever`

### 3. Hierarchical RAG (계층적 검색)

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

**장점:**

- 대규모 문서에서 정밀한 검색
- "Lost in the Middle" 완화
- 컨텍스트 품질 향상

**도입 시점:**

- 문서가 매우 길고 구조화되어 있을 때
- 단일 검색으로 정확도가 부족할 때

### 4. Parent-Child Retrieval (Sentence Window)

작은 청크로 검색하고, 큰 청크로 컨텍스트 제공.

```
인덱싱:
- Parent 청크: 2000 토큰 (LLM 컨텍스트용)
- Child 청크: 200 토큰 (검색용)

검색:
Child로 검색 ──► Parent 청크 반환 ──► LLM
(정밀 검색)      (충분한 문맥)
```

**장점:** 검색 정밀도 + 컨텍스트 완전성 모두 확보

**참고:** [LlamaIndex - Sentence Window Retrieval](https://docs.llamaindex.ai/en/stable/examples/node_postprocessor/MetadataReplacementDemo/)
