# STEP 6.9: 테스트 러너 (Runner)

## 상태: 완료 ✅

## 목표
질문셋 전체 실행, 결과 저장, HTML 리포트 생성

---

## 구현

### 실행 스크립트 (`scripts/run_rag.py`)

```python
# 주요 기능
- 질문셋 로드 및 필터링
- 파이프라인 선택 (minimal/standard/full)
- 결과 저장 (JSON)
- 단계별 타이밍 측정
- HTML 리포트 자동 생성
- 통계 출력
```

### 리포트 생성기 (`scripts/generate_report.py`)

```python
# 주요 기능
- JSON 결과 → HTML 리포트 변환
- 요약 통계 카드
- 단계별 타이밍 바 차트
- 질문별 상세 (예상 정답 vs 실제 답변 비교)
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

# 리포트만 재생성
uv run python scripts/generate_report.py data/results/*.json
```

---

## 결과 파일 형식

```json
{
  "run_id": "20260101_175906",
  "config": {
    "name": "minimal",
    "preprocessor": null,
    "query_builder": "KNNQueryBuilder",
    "search_size": 5
  },
  "results": [
    {
      "id": 1,
      "level": 1,
      "category": "single_retrieval",
      "question": "연차 휴가는 며칠인가?",
      "expected_answer": "근속 연수에 따라 다름: 1년 미만 월 1일...",
      "key_facts": ["1년 미만: 월 1일", "1~3년: 15일", ...],
      "documents_required": ["휴가정책.txt"],
      "answer": "제공된 문서에 따르면...",
      "sources": [{"file_name": "휴가정책.txt", "score": 0.54}],
      "input_tokens": 3063,
      "output_tokens": 357,
      "latency_ms": 7445.8,
      "timings": {
        "embedding": 1036.2,
        "query_build": 0.0,
        "search": 169.2,
        "context_build": 0.0,
        "prompt_render": 0.0,
        "llm": 7212.4
      },
      "model": "claude-sonnet-4-5-20250929"
    }
  ],
  "summary": {...}
}
```

---

## 출력 예시

```
🚀 파이프라인 생성 중... (minimal)
📝 1개 질문 실행 예정

질문 처리: 100%|██████████| 1/1 [00:07<00:00,  7.45s/it]

💾 결과 저장: data/results/20260101_175906_minimal.json
📊 리포트 생성: data/results/20260101_175906_minimal.html

============================================================
📊 실행 결과 요약 (minimal pipeline)
============================================================

총 질문 수: 1
평균 레이턴시: 7445.8ms
최소/최대: 7445.8ms / 7445.8ms

총 토큰: 3,420
  - 입력: 3,063
  - 출력: 357

레벨별 통계:
  Level 1: 1개, 평균 7445.8ms
============================================================
```

---

## HTML 리포트 기능

- **요약 카드**: 총 질문 수, 평균 레이턴시, 토큰 사용량, 모델
- **타이밍 분석**: 단계별 소요시간 바 차트 (embedding, search, llm 등)
- **질문별 상세**: 접기/펼치기 가능한 카드
  - 예상 정답 vs 실제 답변 비교
  - key_facts 태그 표시
  - 소스 문서 목록
  - 단계별 타이밍 상세

---

## 파일 구조

```
scripts/
├── run_rag.py           # 테스트 러너
└── generate_report.py   # HTML 리포트 생성기

data/
├── questions/
│   └── question_set.json  # 18개 질문 (Level 1-4) + 정답
└── results/
    ├── {timestamp}_{pipeline}.json  # 실행 결과
    └── {timestamp}_{pipeline}.html  # HTML 리포트
```

---

## 주요 함수

### run_rag.py

| 함수 | 설명 |
|------|------|
| `load_questions()` | 질문셋 로드 |
| `filter_questions()` | ID/레벨 필터링 |
| `get_pipeline_config()` | 파이프라인 설정 정보 |
| `save_results()` | JSON 결과 저장 |
| `calculate_summary()` | 통계 계산 |
| `print_summary()` | 결과 요약 출력 |

### generate_report.py

| 함수 | 설명 |
|------|------|
| `generate_html_report()` | JSON → HTML 변환 |
| `render_header()` | 헤더 섹션 렌더링 |
| `render_summary()` | 요약 카드 렌더링 |
| `render_timing_analysis()` | 타이밍 바 차트 렌더링 |
| `render_questions()` | 질문별 상세 렌더링 |

---

## 할 일

- [x] run_rag.py 스크립트 작성
- [x] 결과 저장 함수 구현
- [x] 통계 출력 함수 구현
- [x] dry-run 모드 구현
- [x] 질문 필터링 (--questions, --level)
- [x] 실행 테스트 확인
- [x] 결과 파일 확인
- [x] 정답 포함 (expected_answer, key_facts)
- [x] 단계별 타이밍 측정 (timings)
- [x] HTML 리포트 자동 생성

---

## 향후 계획

- [ ] 결과 비교 스크립트 (`compare_runs.py`)
- [ ] LLM 기반 자동 평가 (정답 유사도 채점)
- [ ] 파이프라인 간 A/B 테스트
