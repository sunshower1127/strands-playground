# PLAN 3: 비교 평가 및 튜닝

## 3.1 결과 비교 파이프라인

### A/B 결과 병합
```python
# scripts/compare.py
import pandas as pd

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
            "human_eval": "",      # 사람이 채울 컬럼
            "llm_eval": "",        # LLM이 채울 컬럼
            "winner": "",          # basic / agent / tie
            "notes": "",           # 특이사항 메모
        })

    # CSV로 저장 (사람 평가용)
    df = pd.DataFrame(merged)
    df.to_csv("data/results/comparison.csv", index=False)

    return merged
```

### 결과 파일 포맷
```csv
id,question,answer_basic,answer_agent,latency_basic_ms,latency_agent_ms,tokens_basic,tokens_agent,tool_calls,human_eval,llm_eval,winner,notes
1,"질문1","답변A","답변B",1200,3500,400,1200,2,"","","",""
2,"질문2","답변A","답변B",1100,2800,380,950,1,"","","",""
...
```

### 사람 평가 가이드
```markdown
## 평가 기준

각 질문에 대해 두 답변을 비교하고 다음을 기록:

### human_eval 컬럼
- "A": Basic이 더 좋음
- "B": Agent가 더 좋음
- "T": 동점 (둘 다 비슷)
- "X": 둘 다 부적절

### winner 컬럼
- 최종 승자 기록 (human_eval과 동일하게 시작)

### notes 컬럼
- 특이사항 메모
- 예: "Agent가 재검색해서 더 정확한 정보 찾음"
- 예: "Basic이 더 간결하고 명확함"
- 예: "둘 다 환각 발생"
```

### LLM 평가 스크립트
```python
# src/eval/judge.py
from litellm import completion

JUDGE_PROMPT = """
다음 질문에 대한 두 개의 답변을 비교 평가해주세요.

## 질문
{question}

## 답변 A (Basic RAG)
{answer_a}

## 답변 B (Agent RAG)
{answer_b}

## 평가 기준
1. 정확성: 질문에 정확하게 답변했는가?
2. 완전성: 필요한 정보를 모두 포함했는가?
3. 명확성: 이해하기 쉽게 설명했는가?
4. 관련성: 불필요한 정보 없이 핵심만 답변했는가?

## 출력 형식 (JSON)
{{
  "winner": "A" | "B" | "tie",
  "scores": {{
    "A": {{"accuracy": 1-5, "completeness": 1-5, "clarity": 1-5, "relevance": 1-5}},
    "B": {{"accuracy": 1-5, "completeness": 1-5, "clarity": 1-5, "relevance": 1-5}}
  }},
  "reasoning": "판단 근거를 1-2문장으로"
}}
"""

def evaluate_pair(question: str, answer_a: str, answer_b: str) -> dict:
    response = completion(
        model="vertex_ai/claude-3-sonnet",
        messages=[{
            "role": "user",
            "content": JUDGE_PROMPT.format(
                question=question,
                answer_a=answer_a,
                answer_b=answer_b,
            )
        }],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def run_llm_evaluation(comparison_file: str):
    df = pd.read_csv(comparison_file)

    for idx, row in df.iterrows():
        result = evaluate_pair(
            row["question"],
            row["answer_basic"],
            row["answer_agent"],
        )

        df.at[idx, "llm_eval"] = result["winner"]
        df.at[idx, "llm_scores"] = json.dumps(result["scores"])
        df.at[idx, "llm_reasoning"] = result["reasoning"]

        # 사람 평가가 없으면 LLM 결과를 winner로
        if pd.isna(row["human_eval"]) or row["human_eval"] == "":
            df.at[idx, "winner"] = result["winner"]

    df.to_csv(comparison_file, index=False)
    return df
```

### 불일치 케이스 하이라이트
```python
def find_disagreements(df: pd.DataFrame) -> pd.DataFrame:
    """사람 평가와 LLM 평가가 다른 케이스 추출"""
    disagreements = df[
        (df["human_eval"] != "") &
        (df["human_eval"] != df["llm_eval"])
    ]

    print(f"총 {len(disagreements)}개의 평가 불일치 발견")
    return disagreements
```

---

## 3.2 분석 및 튜닝

### 평가 결과 분석
```python
# scripts/analyze.py
def analyze_results(comparison_file: str):
    df = pd.read_csv(comparison_file)

    # 1. 전체 승률
    winner_counts = df["winner"].value_counts()
    print("=== 전체 승률 ===")
    print(f"Basic 승: {winner_counts.get('A', 0)}")
    print(f"Agent 승: {winner_counts.get('B', 0)}")
    print(f"동점: {winner_counts.get('tie', 0)}")

    # 2. 카테고리별 분석 (질문 유형별)
    if "category" in df.columns:
        print("\n=== 카테고리별 승률 ===")
        category_analysis = df.groupby("category")["winner"].value_counts()
        print(category_analysis)

    # 3. 성능 비교
    print("\n=== 성능 비교 ===")
    print(f"평균 응답시간 - Basic: {df['latency_basic_ms'].mean():.0f}ms")
    print(f"평균 응답시간 - Agent: {df['latency_agent_ms'].mean():.0f}ms")
    print(f"평균 토큰 - Basic: {df['tokens_basic'].mean():.0f}")
    print(f"평균 토큰 - Agent: {df['tokens_agent'].mean():.0f}")

    # 4. Agent 도구 사용 패턴
    print("\n=== Agent 도구 사용 ===")
    print(f"평균 도구 호출: {df['tool_calls'].mean():.1f}회")
    print(f"최대 도구 호출: {df['tool_calls'].max()}회")

    # 5. 비용 추정
    # Claude 3 Sonnet 기준: input $3/1M, output $15/1M
    basic_cost = df['tokens_basic'].sum() * 0.000009  # 대략적 추정
    agent_cost = df['tokens_agent'].sum() * 0.000009
    print(f"\n=== 비용 추정 ===")
    print(f"Basic 총 비용: ${basic_cost:.4f}")
    print(f"Agent 총 비용: ${agent_cost:.4f}")
    print(f"Agent 추가 비용: {(agent_cost/basic_cost - 1)*100:.1f}%")

    return df
```

### 분석 보고서 생성
```python
def generate_report(df: pd.DataFrame, output_path: str):
    report = f"""
# RAG 평가 보고서

## 개요
- 총 질문 수: {len(df)}
- 평가 완료: {df['winner'].notna().sum()}

## 승률 비교
- Basic RAG: {(df['winner'] == 'A').sum()} 승 ({(df['winner'] == 'A').mean()*100:.1f}%)
- Agent RAG: {(df['winner'] == 'B').sum()} 승 ({(df['winner'] == 'B').mean()*100:.1f}%)
- 동점: {(df['winner'] == 'tie').sum()} ({(df['winner'] == 'tie').mean()*100:.1f}%)

## 성능 비교
| 지표 | Basic | Agent | 차이 |
|------|-------|-------|------|
| 평균 응답시간 | {df['latency_basic_ms'].mean():.0f}ms | {df['latency_agent_ms'].mean():.0f}ms | +{df['latency_agent_ms'].mean() - df['latency_basic_ms'].mean():.0f}ms |
| 평균 토큰 | {df['tokens_basic'].mean():.0f} | {df['tokens_agent'].mean():.0f} | +{df['tokens_agent'].mean() - df['tokens_basic'].mean():.0f} |

## Agent가 우수한 케이스
{get_agent_wins_summary(df)}

## Basic이 우수한 케이스
{get_basic_wins_summary(df)}

## 튜닝 권장사항
{generate_recommendations(df)}
"""
    with open(output_path, "w") as f:
        f.write(report)
```

### 튜닝 작업
```python
# 튜닝 포인트

## 1. 프롬프트 튜닝
- Agent 시스템 프롬프트 개선
- 검색 쿼리 생성 가이드 추가
- 답변 포맷 지정

## 2. 검색 파라미터 튜닝
- k (검색 문서 수): 3, 5, 7 비교
- 검색 알고리즘: k-NN vs 하이브리드
- 재검색 조건 설정

## 3. 도구 설계 튜닝
- 도구 설명 개선 (Agent가 더 잘 이해하도록)
- 추가 도구 필요 여부 검토
- 도구 출력 포맷 최적화

## 4. 모드 전환 전략
- 어떤 질문에 Agent를 쓸지 분류기 개발
- 비용 대비 효과 임계값 설정
```

### 반복 실험 스크립트
```python
# scripts/experiment.py
def run_experiment(config: dict, experiment_name: str):
    """다른 설정으로 실험 실행"""

    # 1. 설정 적용
    update_config(config)

    # 2. 테스트 실행
    run_basic()  # 또는 run_agent()

    # 3. 결과 저장 (실험별 폴더)
    save_results(f"data/results/{experiment_name}/")

    # 4. 비교 분석
    compare_with_baseline(experiment_name)


# 실험 예시
experiments = [
    {"name": "k3", "config": {"search_k": 3}},
    {"name": "k7", "config": {"search_k": 7}},
    {"name": "prompt_v2", "config": {"prompt_version": "v2"}},
]

for exp in experiments:
    run_experiment(exp["config"], exp["name"])
```

---

## 🎯 Phase 3 완료 체크리스트

- [ ] A/B 결과 병합 스크립트 완성
- [ ] comparison.csv 생성
- [ ] 사람 평가 완료 (전체 또는 샘플링)
- [ ] LLM 평가 실행 완료
- [ ] 평가 불일치 케이스 분석
- [ ] 분석 보고서 생성
- [ ] 튜닝 방향 도출
- [ ] (선택) 튜닝 후 재실험

**최종 산출물**:
- `data/results/comparison.csv` - 전체 비교 결과
- `data/results/report.md` - 분석 보고서
- 튜닝 권장사항 및 다음 단계 계획
