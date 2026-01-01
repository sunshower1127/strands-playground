# STEP 8: 비교 평가 준비

## 상태: 완료

## 목표

Basic RAG와 Agent RAG의 성능 및 품질 비교 평가

---

## 1. 비교 평가 스크립트

### 사용법

```bash
# 전체 실행 (Basic + Agent)
uv run python scripts/run_comparison.py

# 특정 질문만
uv run python scripts/run_comparison.py --questions 1,2,3

# 레벨 필터
uv run python scripts/run_comparison.py --level 1

# 한 모드만 실행
uv run python scripts/run_comparison.py --mode basic
uv run python scripts/run_comparison.py --mode agent

# 기존 결과로 비교만
uv run python scripts/run_comparison.py --compare-only data/results/basic.json data/results/agent.json

# 설정 확인
uv run python scripts/run_comparison.py --dry-run
```

---

## 2. 출력 파일

| 파일                       | 설명                 |
| -------------------------- | -------------------- |
| `{run_id}_basic.json`      | Basic 모드 전체 결과 |
| `{run_id}_agent.json`      | Agent 모드 전체 결과 |
| `{run_id}_comparison.json` | 병합된 비교 결과     |
| `{run_id}_comparison.html` | 시각화 HTML 리포트   |

---

## 3. 비교 항목

### 정량적 비교

- **레이턴시**: 평균, 최소, 최대
- **토큰 사용량**: 입력, 출력, 총합
- **비용**: USD, KRW (Claude Sonnet 기준)
- **레벨별 분포**: Level 1~4별 성능 차이

### 정성적 비교 (수동 평가)

- **정확성**: 사실이 맞는가?
- **완전성**: 필요한 정보가 다 있는가?
- **관련성**: 질문에 맞는 답변인가?
- **추론력**: 정보를 잘 연결했는가?

---

## 4. 결과 구조

### comparison.json

```json
{
  "run_id": "20260101_120000",
  "type": "comparison",
  "results": [
    {
      "id": 1,
      "level": 1,
      "question": "연차 휴가는 며칠인가?",
      "expected_answer": "근속 연수에 따라 다름...",
      "key_facts": ["1년 미만: 월 1일", "1~3년: 15일", ...],
      "answer_basic": "...",
      "latency_basic_ms": 8600,
      "tokens_basic": 3500,
      "answer_agent": "...",
      "latency_agent_ms": 15000,
      "tokens_agent": 4000,
      "tool_calls": [...],
      "winner": "",
      "notes": ""
    }
  ],
  "stats": {
    "total_questions": 18,
    "basic": {
      "avg_latency_ms": 8500,
      "total_tokens": 60000,
      "cost_usd": 0.0180,
      "cost_krw": 26
    },
    "agent": {
      "avg_latency_ms": 15000,
      "total_tokens": 75000,
      "cost_usd": 0.0225,
      "cost_krw": 33
    },
    "latency_diff_ms": 6500,
    "token_diff": 15000,
    "cost_diff_usd": 0.0045,
    "cost_diff_krw": 7,
    "by_level": {...}
  }
}
```

---

## 5. HTML 리포트 구성

1. **요약 카드** (9개 그리드)
   - 레이턴시: Basic / Agent / 차이
   - 토큰: Basic / Agent / 차이
   - 비용: Basic / Agent / 차이
2. **레벨별 막대 차트**: Basic vs Agent 레이턴시 비교
3. **질문별 상세**: 접기/펼치기 가능한 카드
   - 예상 정답 + 핵심 정보
   - Basic 답변
   - Agent 답변

---

## 6. 할 일

- [x] 비교 평가 스크립트 작성 (`scripts/run_comparison.py`)
- [x] 결과 병합 및 통계 계산 로직
- [x] HTML 리포트 생성
- [x] 비용 계산 모듈 (`src/cost.py`)
- [x] Agent 토큰 누적 버그 수정 (→ STEP 7 문서 참조)
- [ ] 전체 질문셋으로 실행
- [ ] 수동 평가 (winner 기록)
- [ ] 분석 보고서 작성

---

## 7. 다음 단계

### 튜닝 포인트

1. **Agent 시스템 프롬프트 개선**

   - 검색 쿼리 생성 가이드 추가
   - 답변 형식 지정

2. **검색 파라미터 튜닝**

   - k (검색 문서 수): 3, 5, 7 비교
   - 하이브리드 검색 적용

3. **도구 설계 개선**
   - 도구 설명 최적화
   - 추가 도구 검토 (웹 검색 등)

---

## 8. 비용 계산 모듈

### 모델별 가격 (USD per 1M tokens)

| 모델              | Input | Output |
| ----------------- | ----- | ------ |
| Claude Sonnet 4.5 | $3    | $15    |
| Claude Haiku 3.5  | $0.80 | $4     |
| Claude Opus 4.5   | $15   | $75    |

### 환율

- USD → KRW: 1,450원

### 사용법

```python
from src.cost import calculate_cost, format_cost

cost = calculate_cost(
    input_tokens=3000,
    output_tokens=500,
    model="claude-sonnet-4-5-20250929"
)
print(format_cost(cost))  # "$0.0120 (₩17)"
```
