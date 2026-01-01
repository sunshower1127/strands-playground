# STEP 6.9: 테스트 러너 (Runner)

## 상태: 완료 ✅

## 목표
질문셋 전체 실행 및 결과 저장

---

## 구현

### 실행 스크립트 (`scripts/run_rag.py`)

```python
# 주요 기능
- 질문셋 로드 및 필터링
- 파이프라인 선택 (minimal/standard/full)
- 결과 저장 (JSON)
- 통계 출력
```

---

## CLI 인터페이스

```bash
# 기본 실행 (minimal pipeline)
uv run python scripts/run_rag.py

# 파이프라인 선택
uv run python scripts/run_rag.py --pipeline minimal
uv run python scripts/run_rag.py --pipeline standard
uv run python scripts/run_rag.py --pipeline full

# 특정 질문만 실행
uv run python scripts/run_rag.py --questions 1,2,3

# 레벨 필터
uv run python scripts/run_rag.py --level 1

# 설정만 출력 (실행 안 함)
uv run python scripts/run_rag.py --dry-run

# 프로젝트 ID 지정
uv run python scripts/run_rag.py --project-id 334
```

---

## 결과 파일 형식

```json
{
  "run_id": "20260101_133815",
  "config": {
    "name": "minimal",
    "preprocessor": null,
    "query_builder": "KNNQueryBuilder",
    "result_filter": null,
    "context_builder": "SimpleContextBuilder",
    "prompt_template": "SimplePromptTemplate",
    "search_size": 5,
    "search_pipeline": null
  },
  "results": [
    {
      "id": 1,
      "level": 1,
      "category": "single_retrieval",
      "question": "연차 휴가는 며칠인가?",
      "answer": "연차 휴가는 입사 1년차 15일...",
      "sources": [{"file_name": "휴가정책.txt", "score": 0.54}],
      "input_tokens": 3063,
      "output_tokens": 348,
      "latency_ms": 8149.7,
      "model": "claude-sonnet-4-5-20250929"
    }
  ],
  "summary": {
    "total_questions": 1,
    "avg_latency_ms": 8149.7,
    "min_latency_ms": 8149.7,
    "max_latency_ms": 8149.7,
    "total_input_tokens": 3063,
    "total_output_tokens": 348,
    "total_tokens": 3411,
    "by_level": {
      "1": {"count": 1, "avg_latency_ms": 8149.7}
    }
  }
}
```

---

## 출력 예시

```
🚀 파이프라인 생성 중... (minimal)
📝 1개 질문 실행 예정

질문 처리: 100%|██████████| 1/1 [00:08<00:00,  8.15s/it]

💾 결과 저장: data/results/20260101_133815_minimal.json

============================================================
📊 실행 결과 요약 (minimal pipeline)
============================================================

총 질문 수: 1
평균 레이턴시: 8149.7ms
최소/최대: 8149.7ms / 8149.7ms

총 토큰: 3,411
  - 입력: 3,063
  - 출력: 348

레벨별 통계:
  Level 1: 1개, 평균 8149.7ms
============================================================
```

---

## 파일 구조

```
scripts/
└── run_rag.py           # 테스트 러너

data/
├── questions/
│   └── question_set.json  # 18개 질문 (Level 1-4)
└── results/
    └── {timestamp}_{pipeline}.json  # 실행 결과
```

---

## 주요 함수

| 함수 | 설명 |
|------|------|
| `load_questions()` | 질문셋 로드 |
| `filter_questions()` | ID/레벨 필터링 |
| `get_pipeline_config()` | 파이프라인 설정 정보 |
| `save_results()` | JSON 결과 저장 |
| `calculate_summary()` | 통계 계산 |
| `print_summary()` | 결과 요약 출력 |

---

## 할 일

- [x] run_rag.py 스크립트 작성
- [x] 결과 저장 함수 구현
- [x] 통계 출력 함수 구현
- [x] dry-run 모드 구현
- [x] 질문 필터링 (--questions, --level)
- [x] 실행 테스트 확인
- [x] 결과 파일 확인

---

## 향후 계획

- [ ] 결과 비교 스크립트 (`compare_runs.py`)
- [ ] LLM 기반 자동 평가
- [ ] 파이프라인 간 A/B 테스트
