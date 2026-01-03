# STEP CBA: 쿼리 개선기 (QueryEnhancer)

## 상태: 완료

- [x] `NoopQueryEnhancer` 구현
- [x] `LLMQueryEnhancer` 구현

## 목표

대화 히스토리를 활용하여 모호한 질문을 명확한 검색 쿼리로 개선

---

## 배경

### 문제 상황

```
사용자: "Gemini API는 어떻게 사용해?"
AI: "Gemini API는 ... (설명)"
사용자: "그건 어떻게 작동해?"  ← "그건"이 뭘 가리키는지 검색 시스템은 모름
```

### 해결 방법

```
"그건 어떻게 작동해?" + 히스토리 → LLM 분석 → "Gemini API 작동 방식"
```

---

## 기존 프로젝트 로직 분석

### analyze_context_with_flash() 요약

- **입력**: 현재 질문 + 최근 6개 메시지
- **처리**: Gemini Flash로 맥락 분석
- **출력**: 개선된 검색 쿼리

### 주요 특징

1. 히스토리 없으면 원본 반환 (스킵)
2. 최근 6개 메시지만 사용 (user-assistant 3쌍)
3. 메시지당 300자 제한 (토큰 절약)
4. 빠른 모델 사용 (Flash)

---

## 구현할 클래스

### Protocol 정의

```python
class QueryEnhancer(Protocol):
    def enhance(
        self,
        query: str,
        history: list[dict] | None = None
    ) -> str:
        """
        대화 히스토리를 활용해 쿼리 개선

        Args:
            query: 현재 사용자 질문
            history: 대화 히스토리 [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            개선된 쿼리 (또는 원본)
        """
        ...
```

### 1. NoopQueryEnhancer (베이스라인)

```python
class NoopQueryEnhancer:
    """쿼리 개선 안 함 - 원본 그대로 반환"""

    def enhance(self, query: str, history: list[dict] | None = None) -> str:
        return query
```

### 2. LLMQueryEnhancer (권장)

```python
class LLMQueryEnhancer:
    """LLM 기반 쿼리 개선 (기존 Flash 로직 포팅)"""

    SYSTEM_PROMPT = """You are a query rewriter for a document search system.
Your task is to rewrite ambiguous queries into clear search queries."""

    USER_PROMPT = """Recent conversation:
{context}

Current question: "{query}"

Instructions:
1. If the question contains pronouns or references to previous context:
   - Replace them with specific terms from the conversation
   - Example: "그건 어떻게 작동해?" → "Gemini API 작동 방식"
   - Example: "더 자세히 알려줘" → "연차 휴가 정책 상세 내용"

2. If it's an independent question:
   - Return the original question as-is

Return ONLY the rewritten query, nothing else."""

    def __init__(
        self,
        llm_client,  # Vertex AI (Gemini Flash) 또는 다른 빠른 모델
        max_history: int = 6,
        max_content_length: int = 300
    ):
        self.llm = llm_client
        self.max_history = max_history
        self.max_content_length = max_content_length

    def enhance(self, query: str, history: list[dict] | None = None) -> str:
        # 히스토리 없으면 스킵
        if not history or len(history) == 0:
            return query

        # 현재 메시지만 있으면 스킵
        if len(history) == 1:
            return query

        # 최근 N개 메시지만 사용
        recent = history[-self.max_history:]

        # 컨텍스트 구성 (길이 제한)
        context = self._build_context(recent)

        # LLM 호출
        try:
            enhanced = self.llm.generate(
                system=self.SYSTEM_PROMPT,
                user=self.USER_PROMPT.format(context=context, query=query)
            )
            return enhanced.strip() or query
        except Exception as e:
            print(f"⚠️ QueryEnhancer 실패, 원본 반환: {e}")
            return query

    def _build_context(self, messages: list[dict]) -> str:
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # 길이 제한
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
```

---

## 설계 결정

### 왜 별도 STEP으로 분리?

| 구분       | QueryEnhancer (CBA) | Preprocessor (CC) |
| ---------- | ------------------- | ----------------- |
| **입력**   | 질문 + 히스토리     | 질문만            |
| **처리**   | LLM 호출            | 텍스트 정규화     |
| **비용**   | 토큰 비용 발생      | 거의 없음         |
| **조건부** | 히스토리 있을 때만  | 항상 실행         |

### LLM 모델 선택

- **권장**: Gemini Flash, Claude Haiku 등 빠르고 저렴한 모델
- **이유**: 단순 재작성 태스크, 고성능 모델 불필요
- **레이턴시**: 100-300ms 목표

### 히스토리 제한

- **메시지 수**: 최근 6개 (user-assistant 3쌍)
- **메시지 길이**: 300자 제한
- **이유**: 토큰 비용 절감 + 최신 맥락이 가장 중요

---

## 스킵 조건

다음 경우 LLM 호출 없이 원본 반환:

1. `history`가 None 또는 빈 리스트
2. 히스토리에 현재 메시지만 있음 (첫 질문)
3. LLM 호출 실패 시 (fallback)

---

## 파이프라인 위치

```
질문 + 히스토리
       ↓
[CBA: QueryEnhancer] ← 여기
       ↓
[CC: Preprocessor]
       ↓
[CD: QueryBuilder]
       ↓
     ...
```

---

## 테스트 케이스

### 1. 히스토리 없음 → 원본 반환

```python
enhancer = LLMQueryEnhancer(llm)
result = enhancer.enhance("연차 휴가는 며칠이야?", history=None)
assert result == "연차 휴가는 며칠이야?"
```

### 2. 대명사 해소

```python
history = [
    {"role": "user", "content": "Gemini API 사용법 알려줘"},
    {"role": "assistant", "content": "Gemini API는 ... 입니다"},
]
result = enhancer.enhance("그건 어떻게 작동해?", history=history)
# 예상: "Gemini API 작동 방식" 또는 유사한 명확한 쿼리
```

### 3. 독립 질문 → 원본 유지

```python
history = [
    {"role": "user", "content": "날씨 어때?"},
    {"role": "assistant", "content": "오늘 맑습니다"},
]
result = enhancer.enhance("연차 휴가는 며칠이야?", history=history)
# 예상: "연차 휴가는 며칠이야?" (맥락 무관한 새 질문)
```

---

## 평가 지표

### 정성적

- 대명사/지시어가 구체적 용어로 치환되었는가?
- 독립 질문은 원본이 유지되었는가?
- 검색 결과 품질이 개선되었는가?

### 정량적

- LLM 호출 레이턴시 (목표: <300ms)
- 토큰 사용량
- 검색 정확도 변화 (A/B 테스트)

---

## 향후 개선 방향 (v2+)

> **참고**: Strands Agent 사용 시, 아래 기법들은 Agent가 자체적으로 처리할 수 있음.
>
> - History 기반 쿼리 강화: Agent의 대화 컨텍스트 관리로 자동 적용
> - Query Decomposition: Agent가 복잡한 질문을 알아서 분해하여 여러 번 검색할 가능성 높음
> - Multi-Query, HyDE: 프롬프트로 지시 가능
>
> **별도 구현이 필요한 경우**: 비용 최적화 (저렴한 모델 사용), 일관된 동작 보장, 세밀한 제어가 필요할 때
> 비용 최적화 측면에서 요약된 히스토리를 히스토리와 같이 저장시키는 방법도 존재함. -> 추후 가능성 체크

---

### 1. Multi-Query (쿼리 확장)

원본 쿼리를 여러 변형으로 확장하여 검색 범위를 넓힘.

**예시:**

```
입력: "Gemini API 사용법"
      ↓ LLM
출력: ["Gemini API 사용법",
       "Gemini API tutorial",
       "Gemini API 시작하기",
       "Google Gemini SDK example"]
      ↓ 각각 검색 후 결과 병합 (Reciprocal Rank Fusion)
```

**구현:**

```python
from strands import tool

MULTI_QUERY_PROMPT = """다음 검색 쿼리의 변형을 3개 생성하세요.
동의어, 다른 표현, 영어/한국어 혼용 등을 활용하세요.

원본 쿼리: "{query}"

JSON 배열로만 반환: ["변형1", "변형2", "변형3"]"""

@tool
def multi_query_search(query: str) -> str:
    """검색 전에 쿼리를 여러 변형으로 확장합니다"""
    # LLM으로 변형 생성
    response = llm.generate(MULTI_QUERY_PROMPT.format(query=query))
    variants = json.loads(response)

    # 원본 포함
    all_queries = [query] + variants

    # 각각 검색
    all_results = []
    for q in all_queries:
        results = vector_db.search(q, top_k=5)
        all_results.append(results)

    # Reciprocal Rank Fusion으로 병합
    return reciprocal_rank_fusion(all_results)

def reciprocal_rank_fusion(result_lists: list, k: int = 60) -> list:
    """여러 검색 결과를 RRF로 통합"""
    scores = {}
    for results in result_lists:
        for rank, doc in enumerate(results):
            doc_id = doc.id
            if doc_id not in scores:
                scores[doc_id] = 0
            scores[doc_id] += 1 / (k + rank + 1)

    # 점수순 정렬
    sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, score in sorted_docs]
```

---

### 2. Query Decomposition (질문 분해)

복잡한 질문을 단순한 하위 질문들로 분해 후 각각 검색.

**예시:**

```
입력: "A사와 B사의 연차 정책 차이점은?"
      ↓ LLM
출력: ["A사의 연차 정책은?", "B사의 연차 정책은?"]
      ↓ 각각 검색
[A사 문서들, B사 문서들]
      ↓ 통합 후 답변 생성
```

**구현:**

```python
from strands import tool

DECOMPOSE_PROMPT = """다음 질문이 여러 하위 질문으로 분해 가능한지 판단하세요.

질문: "{query}"

분해 가능하면 하위 질문들을 JSON 배열로 반환: ["질문1", "질문2"]
분해 불필요하면 빈 배열 반환: []"""

@tool
def decomposed_search(query: str) -> str:
    """복잡한 질문을 분해하여 검색합니다"""
    # 분해 시도
    response = llm.generate(DECOMPOSE_PROMPT.format(query=query))
    sub_queries = json.loads(response)

    if not sub_queries:
        # 분해 불필요 - 원본으로 검색
        return vector_db.search(query)

    # 각 하위 질문으로 검색
    all_results = []
    for sub_q in sub_queries:
        results = vector_db.search(sub_q, top_k=5)
        all_results.extend(results)

    # 중복 제거 후 반환
    return deduplicate(all_results)
```

**2025 연구 결과:**

| 프레임워크                                                                 | 성능 향상                | 특징                    |
| -------------------------------------------------------------------------- | ------------------------ | ----------------------- |
| [Question Decomposition RAG](https://aclanthology.org/2025.acl-srw.32.pdf) | MRR@10 +36.7%, F1 +11.6% | 분해 → 검색 → Rerank    |
| [HopRAG](https://arxiv.org/html/2502.12442v1)                              | 답변 정확도 +76.78%      | 그래프 기반 다단계 추론 |

**참고:**

- [Haystack - Query Decomposition Cookbook](https://haystack.deepset.ai/cookbook/query_decomposition)
- [MultiHop-RAG Benchmark](https://openreview.net/forum?id=t4eB3zYWBK)

---

### 3. HyDE (Hypothetical Document Embeddings)

질문 대신 가상의 답변을 생성하여 검색. 답변 형태가 실제 문서와 더 유사하므로 검색 품질 향상.

**예시:**

```
입력: "Gemini API 사용법"
      ↓ LLM (가상 답변 생성)
출력: "Gemini API를 사용하려면 먼저 Google Cloud 프로젝트를 생성하고,
       API 키를 발급받습니다. 그 다음 google-generativeai 패키지를
       pip install로 설치한 후, genai.configure(api_key=...)로
       초기화하면 됩니다..."
      ↓ 이 가상 답변을 임베딩해서 검색
[실제 Gemini API 문서들]
```

**구현:**

```python
from strands import tool

HYDE_PROMPT = """다음 질문에 대한 답변을 작성하세요.
실제 정보가 아니어도 됩니다. 그럴듯한 답변 형식으로 작성하세요.
200자 이내로 작성하세요.

질문: "{query}"

답변:"""

@tool
def hyde_search(query: str) -> str:
    """가상 답변을 생성하여 검색합니다"""
    # 가상 답변 생성
    hypothetical_answer = llm.generate(HYDE_PROMPT.format(query=query))

    # 가상 답변으로 검색 (문서와 유사한 형태)
    return vector_db.search(hypothetical_answer, top_k=10)
```

**왜 효과적인가:**

- 질문: "연차 휴가 며칠?" → 짧고 의문형
- 문서: "연차 휴가는 입사 1년 후 15일이 부여됩니다" → 길고 서술형
- 가상 답변이 문서와 형태가 비슷해서 임베딩 유사도가 높아짐

---

### 비용 최적화 전략

```
[Agent에게 전부 맡김]
사용자 질문 → Claude Sonnet (비쌈) → 쿼리 강화 + 분해 + 검색 + 답변
                    ↑ 전부 여기서 처리

[별도 파이프라인]
사용자 질문 → Gemini Flash (저렴) → 쿼리 강화/분해/HyDE
                ↓
           검색 (벡터 DB)
                ↓
           Claude Sonnet → 답변만 생성
```

| 접근법                | 장점                     | 단점                 |
| --------------------- | ------------------------ | -------------------- |
| Agent 프롬프트에 삽입 | 구현 0초                 | 비용 증가, 매번 실행 |
| 별도 도구로 구현      | 선택적 실행, 비용 최적화 | 구현 필요            |
| 아무것도 안함         | 비용 최소                | 검색 품질 제한       |

---

### 참고 논문

- [CHIQ: Contextual History Enhancement](https://arxiv.org/html/2406.05013v1)
- [Query Rewriting in RAG Applications](https://shekhargulati.com/2024/07/17/query-rewriting-in-rag-applications/)

---

## 참고: HyDE와의 관계

| 기술          | QueryEnhancer (CBA) | HyDE (future)       |
| ------------- | ------------------- | ------------------- |
| **목적**      | 대명사/맥락 해소    | 질문→답변 형태 변환 |
| **입력**      | 질문 + 히스토리     | 질문만              |
| **출력**      | 명확한 질문         | 가상 답변 문서      |
| **함께 사용** | 가능                | CBA → HyDE 순서     |

---

## 파일

- `src/rag/query_enhancer.py`
- `tests/test_query_enhancer.py`

---

## 할 일

- [ ] Protocol 정의
- [ ] NoopQueryEnhancer 구현
- [ ] LLMQueryEnhancer 구현
- [ ] Vertex AI (Gemini Flash) 연동
- [ ] 테스트 케이스 작성
- [ ] 레이턴시 측정
