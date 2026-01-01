# STEP 10: LEVEL 2 질문 비교 평가

## 상태: 완료

## 목표

LEVEL 2 (다중 검색) 질문에 대해 Basic RAG와 Agent RAG 비교 평가

---

## 1. 시스템 개선 사항 (이번 단계에서 구현)

### 1.1 max_tokens 에러 해결

**문제**: Q9에서 `MaxTokensReachedException` 발생

```
"answer_agent": "ERROR: Agent has reached an unrecoverable state due to max_tokens limit"
```

**원인**: Agent가 여러 번 검색하면서 컨텍스트가 커져 출력 토큰 1024 초과

**해결**:
```python
# src/agent/rag_agent.py
"max_tokens": 2048,  # 1024 → 2048 증가

# 예외 처리 추가
try:
    result = self.agent(question)
except MaxTokensReachedException as e:
    return AgentRAGResult(
        answer=f"ERROR: {str(e)}",
        call_history=get_call_history(),  # 에러 전까지의 호출 이력 보존
        ...
    )
```

### 1.2 Agent 도구 호출 이력 추가

**목적**: Agent가 어떤 순서로 도구를 호출했는지, 어떤 검색 쿼리를 사용했는지 추적

**구현**:
```python
# src/agent/tools/search.py
_call_history: list[dict] = []

@tool
def search_documents(query: str, k: int = 5) -> str:
    _call_history.append({
        "call_index": len(_call_history) + 1,
        "tool": "search_documents",
        "query": query,
        "elapsed_ms": round(elapsed_ms, 1),
        "result_count": len(results),
        "documents": [
            {"rank": i, "file_name": fname, "score": score, "text_preview": text[:100]}
            for i, (fname, score, text) in enumerate(results, 1)
        ],
    })
```

**결과 예시** (`comparison.json`):
```json
"call_history": [
  {
    "call_index": 1,
    "tool": "search_documents",
    "query": "휴가 재택근무 동시 사용",
    "elapsed_ms": 1205.6,
    "result_count": 3,
    "documents": [
      {"rank": 1, "file_name": "재택가이드.txt", "score": 0.4573, "text_preview": "..."}
    ]
  }
]
```

### 1.3 Agent 호출 로그 파일 생성

**파일**: `{run_id}_agent_calls.log`

**형식**:
```
================================================================================
Agent RAG 도구 호출 로그 - 20260101_214038
================================================================================

--------------------------------------------------------------------------------
Q5: 휴가와 재택근무를 동시에 사용할 수 있나?
--------------------------------------------------------------------------------
  [1] search_documents
      Query: "휴가 재택근무 동시 사용"
      Results: 3개 (1205.6ms)
        #1 [0.457] 재택가이드.txt
            "재택근무일에 휴가(반차 포함)를 사용할 수 있습니다..."

  → 답변: 네, 휴가와 재택근무를 동시에 사용할 수 있습니다...
  → 정확도: 67%
```

---

## 2. LEVEL 2 비교 결과

### 테스트 실행 정보

- **Run ID**: 20260101_214038
- **질문 수**: 5개
- **카테고리**: multi_retrieval (다중 문서 검색)

### 2.1 전체 성능 비교

| 항목 | Basic | Agent | 차이 |
|------|-------|-------|------|
| 평균 레이턴시 | 10,936ms | 16,934ms | +55% |
| 입력 토큰 | 29,168 | 35,144 | +20% |
| 출력 토큰 | 2,489 | 4,142 | +66% |
| 총 토큰 | 31,657 | 39,286 | +24% |
| 비용 (USD) | $0.125 | $0.168 | +34% |
| 비용 (KRW) | ₩181 | ₩243 | +34% |

### 2.2 정확도 비교

| 항목 | Basic | Agent |
|------|-------|-------|
| 평균 정확도 | 77.8% | **88.9%** |
| 완벽 매칭 | 2개 | 2개 |
| 매칭된 facts | 7개 | **8개** |

### 2.3 효율성 비교

| 항목 | Basic | Agent | 비율 |
|------|-------|-------|------|
| tokens/fact | 4,522 | 4,911 | 1.09x |
| ms/fact | 7,811 | 10,584 | 1.35x |
| ₩/fact | ₩25.86 | ₩30.37 | 1.17x |

### 2.4 질문별 결과

| Q | 질문 | Basic 정확도 | Agent 정확도 | 승자 | 비고 |
|---|------|-------------|--------------|------|------|
| 5 | 휴가+재택 동시 사용? | 33% | **67%** | Agent | Agent 쿼리 우수 |
| 6 | 복지 포인트 항목? | 100% | 100% | 무승부 | key_facts 없음 |
| 7 | Q3 FlowSync 신기능? | 100% | 100% | 무승부 | key_facts 없음 |
| 8 | API 401 vs 403 차이? | **100%** | **100%** | 무승부 | 둘 다 완벽 |
| 9 | 최근 3개월 변경사항? | **100%** | **100%** | 무승부 | max_tokens 해결 후 |

---

## 3. 분석

### 3.1 Agent 개선점

1. **Q5 검색 쿼리 우수**
   - Basic: 원본 질문 그대로 검색 → 관련 없는 문서도 포함
   - Agent: `"휴가 재택근무 동시 사용"` 핵심 키워드 추출 → 정확한 검색

2. **Q9 해결**
   - max_tokens 증가 (1024 → 2048)로 정상 동작
   - 출력 토큰 1,842개 사용 (증가된 한도 내)

### 3.2 LEVEL 1 vs LEVEL 2 비교

| 항목 | LEVEL 1 | LEVEL 2 |
|------|---------|---------|
| 정확도 | Basic 92% > Agent 67% | Agent 89% > Basic 78% |
| 속도 | Basic +44% 빠름 | Agent +55% 느림 |
| 비용 | Basic -43% 저렴 | Agent +34% 비쌈 |
| 권장 | **Basic** | **Agent** (정확도 우선) |

### 3.3 LEVEL 2 결론

**다중 검색 질문에서는 Agent RAG가 우수**

- Agent가 검색 쿼리를 최적화하여 더 정확한 결과
- 비용/속도 차이는 있지만 정확도 11%p 향상
- 복잡한 질문일수록 Agent의 자율 판단이 효과적

---

## 4. 수정된 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/agent/rag_agent.py` | max_tokens 증가, MaxTokensReachedException 처리, call_history 추가 |
| `src/agent/tools/search.py` | 로깅 추가, _call_history 저장, get_call_history() 함수 |
| `src/agent/service.py` | call_history 전달 |
| `src/types.py` | ServiceResult에 call_history 필드 추가 |
| `scripts/run_comparison.py` | call_history 병합, save_agent_call_log() 함수 추가 |

---

## 5. 새 출력 파일

### 5.1 comparison.json 추가 필드

```json
{
  "call_history": [
    {
      "call_index": 1,
      "tool": "search_documents",
      "query": "휴가 재택근무 동시 사용",
      "k": 5,
      "elapsed_ms": 1205.6,
      "result_count": 3,
      "documents": [
        {
          "rank": 1,
          "file_name": "재택가이드.txt",
          "score": 0.4573,
          "text_preview": "재택근무일에 휴가(반차 포함)를 사용할 수 있습니다..."
        }
      ]
    }
  ]
}
```

### 5.2 agent_calls.log

Agent 도구 호출 흐름을 읽기 쉬운 텍스트로 출력:
- 질문별 도구 호출 순서
- 검색 쿼리와 결과
- 각 문서의 파일명, 점수, 미리보기
- 최종 답변과 정확도

---

## 6. 다음 단계

### 6.1 LEVEL 3-4 테스트

- [ ] LEVEL 3 (추론) 테스트
- [ ] LEVEL 4 (복합) 테스트
- Agent의 다단계 추론/복합 질문 처리 능력 검증

### 6.2 추가 분석

- [ ] 검색 쿼리 품질 분석 (Agent vs 원본 질문)
- [ ] 도구 호출 횟수별 정확도 상관관계
- [ ] 검색 실패 시 재검색 패턴 분석

---

## 7. 결론

### LEVEL 2 결과 요약

| 평가 항목 | 승자 |
|----------|------|
| 정확도 | **Agent RAG** (89% vs 78%) |
| 속도 | Basic RAG |
| 비용 | Basic RAG |
| 효율성 | Basic RAG |

### 권장 사항

| 레벨 | 권장 모드 | 이유 |
|------|----------|------|
| LEVEL 1 (단순 검색) | Basic RAG | 빠르고 저렴, 충분히 정확 |
| LEVEL 2 (다중 검색) | **Agent RAG** | 검색 쿼리 최적화로 더 정확 |

**결론**: 질문 복잡도에 따라 모드 선택 필요. Agent는 복잡한 질문에서 강점을 보이나 비용/속도 트레이드오프 존재.
