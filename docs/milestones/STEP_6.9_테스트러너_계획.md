# STEP CI: 테스트 러너 (Runner)

## 상태: 계획

## 목표
질문셋 전체 실행 및 결과 저장

---

## 구현

### 실행 스크립트

```python
# scripts/run_rag.py

def main():
    # 1. 파이프라인 생성
    pipeline = create_minimal_pipeline()  # 또는 create_full_pipeline()

    # 2. 질문셋 로드
    questions = load_questions("data/questions/question_set.json")

    # 3. 실행
    results = []
    for q in tqdm(questions):
        result = pipeline.query(q["question"])
        results.append({
            "id": q["id"],
            "level": q["level"],
            "category": q["category"],
            "question": q["question"],
            "answer": result.answer,
            "sources": [s["_source"].get("file_name") for s in result.sources],
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
        })

    # 4. 결과 저장
    save_results(results, pipeline_config)

    # 5. 통계 출력
    print_summary(results)
```

---

## 결과 파일 형식

```json
{
  "run_id": "20241231_160000",
  "config": {
    "preprocessor": "NoopPreprocessor",
    "query_builder": "KNNQueryBuilder",
    "result_filter": null,
    "context_builder": "SimpleContextBuilder",
    "prompt_template": "SimplePromptTemplate"
  },
  "results": [
    {
      "id": 1,
      "level": 1,
      "category": "single_retrieval",
      "question": "연차 휴가는 며칠인가?",
      "answer": "연차 휴가는 입사 1년차 15일...",
      "sources": ["휴가정책.md"],
      "input_tokens": 500,
      "output_tokens": 150,
      "latency_ms": 1234.5
    },
    ...
  ],
  "summary": {
    "total_questions": 18,
    "avg_latency_ms": 1500.0,
    "total_input_tokens": 9000,
    "total_output_tokens": 2700,
    "by_level": {
      "1": {"count": 4, "avg_latency_ms": 1200.0},
      "2": {"count": 5, "avg_latency_ms": 1400.0},
      "3": {"count": 5, "avg_latency_ms": 1600.0},
      "4": {"count": 4, "avg_latency_ms": 1800.0}
    }
  }
}
```

---

## CLI 인터페이스

```bash
# 기본 실행 (minimal pipeline)
uv run python scripts/run_rag.py

# 옵션
uv run python scripts/run_rag.py --pipeline full
uv run python scripts/run_rag.py --questions 1,2,3  # 특정 질문만
uv run python scripts/run_rag.py --dry-run  # 설정만 출력
```

---

## 결과 비교 스크립트 (향후)

```python
# scripts/compare_runs.py
# 두 실행 결과 비교
# - latency 차이
# - 답변 품질 (수동 평가용 출력)
# - 토큰 사용량 비교
```

---

## 파일
- `scripts/run_rag.py`
- `data/results/` (결과 저장 폴더)

---

## 할 일
- [ ] run_rag.py 스크립트 작성
- [ ] 결과 저장 함수 구현
- [ ] 통계 출력 함수 구현
- [ ] 전체 질문셋 실행 테스트
- [ ] 결과 파일 확인
