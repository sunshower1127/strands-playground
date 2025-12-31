# STEP B: OpenSearch CLI 통합 및 테스트 구조

## 상태: 완료

## 할 일
- [x] OpenSearch CLI 도구 통합 (`scripts/opensearch/cli.py`)
- [x] pytest 테스트 구조 설정
- [x] 기존 분산 스크립트 정리

---

## 1. OpenSearch CLI

모든 OpenSearch 관련 명령어를 하나의 CLI 도구로 통합.

### 사용법

```bash
# Makefile 통해서
make os CMD="test"
make os CMD="explore"
make os CMD="count 300"
make os CMD="collect 300"
make os CMD="get-doc 123"

# 직접 실행
uv run python scripts/opensearch/cli.py count 300
uv run python scripts/opensearch/cli.py get-doc 123 --index other-index
```

### 명령어 목록

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `test` | 연결 테스트 | `make os CMD="test"` |
| `explore [index]` | 인덱스 구조 탐색 | `make os CMD="explore"` |
| `count <project_id>` | 프로젝트별 청크 개수 | `make os CMD="count 300"` |
| `collect <project_id>` | 텍스트 수집 | `make os CMD="collect 300"` |
| `get-doc <document_id>` | 문서 조회 | `make os CMD="get-doc 123"` |

## 2. pytest 테스트 구조

```
tests/
├── __init__.py
├── conftest.py              # 공통 fixtures
└── test_opensearch_client.py  # OpenSearchClient 테스트
```

### 실행

```bash
make test
```

### Fixtures (conftest.py)

- `opensearch_client`: OpenSearchClient 인스턴스
- `test_index`: 테스트용 기본 인덱스명

## 3. OpenSearchClient 메서드

| 메서드 | 설명 |
|--------|------|
| `get_info()` | 클러스터 정보 |
| `list_indices()` | 인덱스 목록 |
| `get_doc_count(index)` | 인덱스 문서 개수 |
| `get_doc_count_by_project(index, project_id)` | 프로젝트별 청크 개수 |
| `get_sample_docs(index, size)` | 샘플 문서 조회 |
| `get_index_mapping(index)` | 인덱스 매핑 정보 |
| `get_docs_by_project(index, project_id)` | 프로젝트별 문서 조회 |
| `get_all_docs_by_project(index, project_id)` | 프로젝트별 전체 문서 (scroll) |
| `get_texts_by_project(index, project_id)` | 프로젝트별 텍스트 추출 |
| `search(index, query, size)` | 커스텀 검색 |

## 4. Makefile 정리

```makefile
.PHONY: format lint tunnel dashboard test os

tunnel:     # SSH 터널 열기
format:     # 코드 포맷팅 (ruff)
lint:       # 린트 검사 (ruff)
dashboard:  # OpenSearch 대시보드 열기
test:       # pytest 실행
os:         # OpenSearch CLI (make os CMD="...")
```
