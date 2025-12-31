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

> 현재는 v1 (기존 로직 포팅)으로 시작. 평가 후 필요시 아래 기법 도입 검토.
> 상세 내용은 `docs/future_improvements.md` 참고.

| 버전     | 기법                     | 복잡도   | 효과             | 비고                         |
| -------- | ------------------------ | -------- | ---------------- | ---------------------------- |
| **v1**   | LLM Rewriting (현재)     | ⭐       | 베이스라인       | 기존 로직 포팅               |
| **v1.1** | + 증분 요약 저장         | ⭐⭐     | 토큰 절감        | 히스토리 길어질 때 도입 검토 |
| **v2**   | + Topic Switch Detection | ⭐⭐     | 노이즈 감소      | 주제 전환 시 히스토리 무시   |
| **v3**   | + Multi-Query (2-3개)    | ⭐⭐⭐   | 검색 범위 확장   | RAG Fusion 방식              |
| **v4**   | + HyDE 결합              | ⭐⭐⭐⭐ | 의미적 매칭 강화 | 가상 답변 임베딩             |

### v1.1 증분 요약 저장 (토큰 최적화)

> 히스토리가 길어질수록 QueryEnhancer 부담 측정 후 도입 검토

```
[현재 v1]
매 턴: 히스토리 6개 메시지 (~1800자) → LLM → 쿼리 개선

[v1.1 제안]
답변 시: context_summary 생성하여 히스토리와 함께 저장
검색 시: 요약 (~50자) + 현재 질문만 → LLM → 쿼리 개선
```

**도입 기준**: QueryEnhancer 토큰 사용량/레이턴시가 병목이 될 때

### CHIQ 방식 (연구 참고)

- **QD** (Question Disambiguation): 대명사/약어 해소
- **RE** (Response Expansion): AI 응답 확장
- **PR** (Pseudo Response): 예상 답변 생성
- **TS** (Topic Switch): 주제 전환 감지
- **HS** (History Summary): 히스토리 요약

→ 각 역할 분리로 정확도 향상, 단 LLM 호출 증가로 비용/레이턴시 트레이드오프

### 참고 논문

- [CHIQ: Contextual History Enhancement](https://arxiv.org/html/2406.05013v1)
- [Query Rewriting in RAG Applications](https://shekhargulati.com/2024/07/17/query-rewriting-in-rag-applications/)

### v5 Query Decomposition (질문 분해)

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

**2025 연구 결과:**

| 프레임워크 | 성능 향상 | 특징 |
|-----------|----------|------|
| [Question Decomposition RAG](https://aclanthology.org/2025.acl-srw.32.pdf) | MRR@10 +36.7%, F1 +11.6% | 분해 → 검색 → Rerank |
| [HopRAG](https://arxiv.org/html/2502.12442v1) | 답변 정확도 +76.78% | 그래프 기반 다단계 추론 |

**도입 시점:**
- 비교 질문이 많을 때 ("A와 B의 차이", "X vs Y")
- 다단계 추론이 필요한 질문
- 단일 검색으로 답변 품질이 낮을 때

**참고:**
- [Haystack - Query Decomposition Cookbook](https://haystack.deepset.ai/cookbook/query_decomposition)
- [MultiHop-RAG Benchmark](https://openreview.net/forum?id=t4eB3zYWBK)

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
