# STEP 9: LEVEL 1 질문 비교 평가

## 상태: 완료

## 목표

LEVEL 1 (단순 검색) 질문에 대해 Basic RAG와 Agent RAG 비교 평가 및 시스템 개선

---

## 1. 시스템 개선 사항 (이번 단계에서 구현)

### 1.1 토큰 Input/Output 분리

**변경 전:**
```json
"tokens_basic": 3430
```

**변경 후:**
```json
"tokens_basic": {
  "input": 3063,
  "output": 371,
  "total": 3434
}
```

- 정확한 비용 계산 가능 (9:1 추정 로직 제거)
- Input/Output 토큰 비율 분석 가능

### 1.2 Key Facts 자동 매칭

```json
"key_facts": ["1년 미만: 월 1일", "1~3년: 15일", ...],
"key_facts_matched_basic": ["1년 미만: 월 1일", "1~3년: 15일", ...],
"key_facts_missed_basic": [],
"accuracy_basic": 1.0
```

- 답변에서 핵심 정보 포함 여부 자동 체크
- 정확도(accuracy) 자동 계산
- 누락된 정보(missed) 추적

### 1.3 효율성 지표

```json
"efficiency": {
  "basic": {
    "tokens_per_fact": 1920.0,
    "latency_per_fact_ms": 2770.8,
    "cost_per_fact_krw": 10.52
  },
  "agent": {
    "tokens_per_fact": 4835.1,
    "latency_per_fact_ms": 6825.9,
    "cost_per_fact_krw": 25.68
  }
}
```

- 매칭된 fact당 비용/시간/토큰 효율성 계산

### 1.4 Agent sources 기록

```json
"sources_agent": [
  {
    "file_name": "기능가이드.txt",
    "score": 0.641665,
    "query": "FlowSync 주요 기능"
  }
]
```

- Agent 모드에서도 검색된 소스 기록
- 검색 쿼리도 함께 저장

### 1.5 Agent 단계별 타이밍

```json
"timings_agent": {
  "total": 10727.2,
  "tool_calls": 365.5,
  "llm": 10361.8
}
```

- 전체 시간 중 도구 호출 vs LLM 시간 분리

---

## 2. LEVEL 1 비교 결과

### 테스트 실행 정보

- **Run ID**: 20260101_205550
- **질문 수**: 4개
- **카테고리**: single_retrieval

### 2.1 전체 성능 비교

| 항목 | Basic | Agent | 차이 |
|------|-------|-------|------|
| 평균 레이턴시 | 8,313ms | 11,945ms | +44% |
| 입력 토큰 | 21,548 | 31,977 | +48% |
| 출력 토큰 | 1,492 | 1,869 | +25% |
| 총 토큰 | 23,040 | 33,846 | +47% |
| 비용 (USD) | $0.087 | $0.124 | +43% |
| 비용 (KRW) | ₩126 | ₩180 | +43% |

### 2.2 정확도 비교

| 항목 | Basic | Agent |
|------|-------|-------|
| 평균 정확도 | 91.7% | 66.7% |
| 완벽 매칭 | 3개 | 2개 |
| 매칭된 facts | 12개 | 7개 |

### 2.3 효율성 비교

| 항목 | Basic | Agent | 비율 |
|------|-------|-------|------|
| tokens/fact | 1,920 | 4,835 | 2.5x |
| ms/fact | 2,771 | 6,826 | 2.5x |
| ₩/fact | ₩10.52 | ₩25.68 | 2.4x |

### 2.4 질문별 결과

| Q | 질문 | Basic 정확도 | Agent 정확도 | 비고 |
|---|------|-------------|--------------|------|
| 1 | 연차 휴가는 며칠인가? | 100% | 0% | Agent 검색 실패 |
| 2 | FlowSync 주요 기능 3가지? | 100% | 100% | 동등 |
| 3 | 재택근무 신청 방법? | 67% | 67% | 동등 (정기 재택 누락) |
| 4 | 현재 FlowSync 버전? | 100% | 100% | 동등 |

---

## 3. 분석

### 3.1 Basic RAG 강점

1. **더 빠름**: 44% 빠른 응답
2. **더 저렴**: 43% 낮은 비용
3. **더 정확**: LEVEL 1에서는 91.7% vs 66.7%
4. **안정적**: 검색 실패 없음

### 3.2 Agent 문제점

1. **Q1 검색 실패**: 4번 검색했지만 관련 문서 못 찾음
   - `sources_agent: []` (검색 결과 비어있음)
   - 원인: 검색 쿼리 품질 문제 또는 임베딩 불일치
2. **토큰 과다 사용**: 48% 더 많은 입력 토큰
3. **비효율적**: fact당 2.5배 비용

### 3.3 LEVEL 1 결론

**단순 검색 질문에서는 Basic RAG가 우수**

- 고정 파이프라인이 더 안정적
- Agent의 자율 판단이 오히려 비효율
- 검색 쿼리 품질 개선 필요

---

## 4. 수정된 파일

| 파일 | 변경 내용 |
|------|----------|
| `scripts/run_comparison.py` | check_key_facts, 토큰 분리, 효율성 지표, sources/timings 병합 |
| `src/agent/tools/search.py` | sources 저장 로직 추가 |
| `src/agent/rag_agent.py` | sources, timings 필드 추가 |
| `src/agent/service.py` | sources, timings 전달 |

---

## 5. 새 결과 포맷

### comparison.json 구조 (개선 후)

```json
{
  "id": 1,
  "question": "연차 휴가는 며칠인가?",
  "key_facts": ["1년 미만: 월 1일", ...],

  // Basic 결과
  "tokens_basic": {"input": 3063, "output": 371, "total": 3434},
  "sources_basic": [{"file_name": "휴가정책.txt", "score": 0.54}],
  "timings_basic": {"embedding": 1075, "search": 143, "llm": 7428},
  "key_facts_matched_basic": [...],
  "accuracy_basic": 1.0,

  // Agent 결과
  "tokens_agent": {"input": 7986, "output": 383, "total": 8369},
  "sources_agent": [{"file_name": "...", "score": 0.64, "query": "..."}],
  "timings_agent": {"total": 17387, "tool_calls": 2238, "llm": 15150},
  "key_facts_matched_agent": [...],
  "accuracy_agent": 0.0
}
```

### stats 구조 (개선 후)

```json
{
  "basic": {
    "avg_latency_ms": 8312.5,
    "tokens": {"input": 21548, "output": 1492, "total": 23040},
    "cost_usd": 0.087,
    "cost_krw": 126
  },
  "accuracy": {
    "basic_avg": 0.9167,
    "agent_avg": 0.6667,
    "basic_perfect": 3,
    "agent_perfect": 2
  },
  "efficiency": {
    "basic": {"tokens_per_fact": 1920, "latency_per_fact_ms": 2771, "cost_per_fact_krw": 10.52},
    "agent": {"tokens_per_fact": 4835, "latency_per_fact_ms": 6826, "cost_per_fact_krw": 25.68}
  },
  "matched_facts": {"basic": 12, "agent": 7}
}
```

---

## 6. 다음 단계

### 6.1 Agent 개선 필요

- [ ] 검색 쿼리 품질 개선 (시스템 프롬프트 튜닝)
- [ ] 검색 실패 시 재시도 로직
- [ ] 검색 결과 없을 때 fallback 전략

### 6.2 LEVEL 2-4 테스트

- [ ] LEVEL 2 (다중 검색) 테스트
- [ ] LEVEL 3 (추론) 테스트
- [ ] LEVEL 4 (복합) 테스트
- Agent의 다중 검색/추론 능력 비교

### 6.3 추가 분석

- [ ] 타이밍 분석 (임베딩 vs 검색 vs LLM)
- [ ] 검색 쿼리 품질 분석
- [ ] 검색 score 분포 분석

---

## 7. 결론

LEVEL 1 단순 검색 질문에서:

| 평가 항목 | 승자 |
|----------|------|
| 속도 | Basic RAG |
| 비용 | Basic RAG |
| 정확도 | Basic RAG |
| 효율성 | Basic RAG |

**LEVEL 1 권장**: Basic RAG 사용

Agent RAG는 복잡한 질문(LEVEL 2-4)에서 진가를 발휘할 것으로 예상되므로 추가 테스트 필요.
