# STEP F: 비교 평가 및 튜닝

## 상태: 계획

## 할 일
- [ ] A/B 결과 병합 스크립트
- [ ] 수동 평가 실행 (18개 질문)
- [ ] 분석 보고서 생성
- [ ] 튜닝 방향 도출
- [ ] (선택) 튜닝 후 재실험

---

## 1. 결과 비교 파이프라인

### A/B 결과 병합
```python
# scripts/compare.py
def merge_results():
    basic = load_json("data/results/basic_results.json")
    agent = load_json("data/results/agent_results.json")

    merged = []
    for b, a in zip(basic["results"], agent["results"]):
        merged.append({
            "id": b["id"],
            "question": b["question"],
            "answer_basic": b["answer"],
            "answer_agent": a["answer"],
            "latency_basic_ms": b["latency_ms"],
            "latency_agent_ms": a["latency_ms"],
            "tokens_basic": b["tokens_used"],
            "tokens_agent": a["tokens_used"],
            "tool_calls": a["tool_call_count"],
            "winner": "",
            "notes": "",
        })

    df = pd.DataFrame(merged)
    df.to_csv("data/results/comparison.csv", index=False)
```

## 2. 수동 평가 가이드

각 질문에 대해 두 답변을 비교:

### 평가 항목
| 항목 | 설명 |
|------|------|
| **정확성** | 사실이 맞는가? |
| **완전성** | 필요한 정보가 다 있는가? |
| **관련성** | 질문에 맞는 답변인가? |
| **추론력** | 정보를 잘 연결했는가? |

### winner 컬럼
- `basic`: Basic RAG가 더 좋음
- `agent`: Agent RAG가 더 좋음
- `tie`: 동점

### 결과 기록 형식
```markdown
## Q1: 연차 휴가는 며칠인가?

### Without Agent
[답변 내용]
- 정확성: O/X
- 완전성: O/X

### With Agent
[답변 내용]
- 정확성: O/X
- 완전성: O/X

### 비교
- 승자: Agent / Basic / 동일
- 차이점: ...
```

## 3. 분석 보고서

```python
def analyze_results(comparison_file: str):
    df = pd.read_csv(comparison_file)

    # 전체 승률
    winner_counts = df["winner"].value_counts()
    print(f"Basic 승: {winner_counts.get('basic', 0)}")
    print(f"Agent 승: {winner_counts.get('agent', 0)}")
    print(f"동점: {winner_counts.get('tie', 0)}")

    # 성능 비교
    print(f"평균 응답시간 - Basic: {df['latency_basic_ms'].mean():.0f}ms")
    print(f"평균 응답시간 - Agent: {df['latency_agent_ms'].mean():.0f}ms")

    # Agent 도구 사용 패턴
    print(f"평균 도구 호출: {df['tool_calls'].mean():.1f}회")
```

## 4. 튜닝 포인트

### 프롬프트 튜닝
- Agent 시스템 프롬프트 개선
- 검색 쿼리 생성 가이드 추가

### 검색 파라미터 튜닝
- k (검색 문서 수): 3, 5, 7 비교
- 검색 알고리즘: k-NN vs 하이브리드

### 도구 설계 튜닝
- 도구 설명 개선
- 추가 도구 필요 여부 검토

---

## 최종 산출물
- `data/results/comparison.csv` - 전체 비교 결과
- `data/results/report.md` - 분석 보고서
- 튜닝 권장사항 및 다음 단계 계획
