# PLAN 1: 기존 RAG 로직 테스트 환경 구축

## 1.1 프로젝트 초기 설정

### Python 프로젝트 구조 생성
```
strands-playground/
├── pyproject.toml
├── src/
│   └── __init__.py
├── tests/
├── data/
└── scripts/
```
- `pyproject.toml`로 의존성 관리 (poetry 또는 pip)
- src 레이아웃으로 import 충돌 방지

### 의존성 설정
```toml
[project]
dependencies = [
    "opensearch-py",      # OpenSearch 연결
    "litellm",            # LLM 통합 (Vertex AI Claude)
    "python-dotenv",      # 환경변수 로드
    "pydantic",           # 데이터 검증
    "pandas",             # 결과 파일 처리
]
```

### 환경변수 설정
```env
# .env.example
OPENSEARCH_HOST=https://your-opensearch-endpoint
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=xxx
OPENSEARCH_INDEX=your-index

GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
VERTEX_PROJECT=your-gcp-project
VERTEX_LOCATION=us-east5
```

---

## 1.2 기존 RAG 로직 재구현

### 기존 로직 코드 분석
- 사용자가 기존 코드 제공하면 분석
- 핵심 로직 파악: 검색 쿼리 구성, 프롬프트 템플릿, 후처리 등

### OpenSearch 연결 모듈
```python
# src/opensearch_client.py
class OpenSearchClient:
    def __init__(self, host, username, password):
        self.client = OpenSearch(...)

    def search(self, query: str, index: str, k: int = 5) -> list[Document]:
        # 벡터 검색 또는 하이브리드 검색
        pass
```

### 검색(retrieval) 로직
- 쿼리 임베딩 생성 (기존 모델 사용)
- k-NN 검색 또는 하이브리드 검색
- 결과 문서 파싱 및 반환

### LLM 호출 로직
```python
# src/llm_client.py
from litellm import completion

def call_llm(prompt: str, context: str) -> str:
    response = completion(
        model="vertex_ai/claude-3-sonnet",
        messages=[{"role": "user", "content": f"{context}\n\n{prompt}"}],
        vertex_project=os.getenv("VERTEX_PROJECT"),
        vertex_location=os.getenv("VERTEX_LOCATION"),
    )
    return response.choices[0].message.content
```

### 기본 RAG 파이프라인
```python
# src/rag/basic.py
class BasicRAG:
    def __init__(self, search_client, llm_client):
        self.search = search_client
        self.llm = llm_client

    def query(self, question: str) -> RAGResult:
        # 1. 검색
        docs = self.search.search(question, k=5)
        # 2. 컨텍스트 구성
        context = self._build_context(docs)
        # 3. LLM 호출
        answer = self.llm.call(question, context)
        # 4. 결과 반환
        return RAGResult(question, answer, docs, metadata)
```

---

## 1.3 문서 및 질문셋 준비

### 테스트 문서 업로드
- 사용자가 OpenSearch에 직접 업로드
- 또는 업로드 스크립트 제공 (필요시)

### 문서 텍스트 파일 수신
- 사용자가 PDF에서 텍스트 추출하여 전달
- 형식: 단일 텍스트 파일 또는 문서별 분리

### 질문셋 생성
```python
# Claude가 텍스트 기반으로 질문 생성
질문 유형 분포 (30-50개):
├── 단순 사실 질문 (40%): "X는 무엇인가요?"
├── 비교/분석 질문 (20%): "A와 B의 차이점은?"
├── 다단계 추론 (20%): "X 상황에서 Y를 하려면?"
├── 엣지 케이스 (15%): 모호하거나 문서에 없는 질문
└── 복합 질문 (5%): 여러 주제를 묻는 질문
```

### 질문셋 검수 및 확정
- 생성된 질문셋을 사용자가 검토
- 부적절한 질문 제거/수정
- 최종 질문셋 JSON 저장

```json
// data/questions.json
[
  {"id": 1, "question": "...", "category": "fact", "difficulty": "easy"},
  {"id": 2, "question": "...", "category": "reasoning", "difficulty": "medium"},
  ...
]
```

---

## 1.4 테스트 실행 및 결과 출력

### 테스트 실행 스크립트
```python
# scripts/run_basic.py
def main():
    rag = BasicRAG(...)
    questions = load_questions("data/questions.json")
    results = []

    for q in questions:
        start = time.time()
        result = rag.query(q["question"])
        elapsed = time.time() - start

        results.append({
            "id": q["id"],
            "question": q["question"],
            "answer": result.answer,
            "sources": [d.id for d in result.docs],
            "latency_ms": elapsed * 1000,
            "tokens_used": result.metadata.tokens,
        })

    save_results(results, "data/results/basic_results.json")
```

### 결과 파일 포맷
```json
// data/results/basic_results.json
{
  "run_id": "basic_20241230_143000",
  "config": {"model": "claude-3-sonnet", "k": 5},
  "results": [
    {
      "id": 1,
      "question": "...",
      "answer": "...",
      "sources": ["doc_1", "doc_3"],
      "latency_ms": 1234,
      "tokens_used": 567
    },
    ...
  ],
  "summary": {
    "total_questions": 50,
    "avg_latency_ms": 1500,
    "total_tokens": 28000
  }
}
```

### 성능 지표 수집
- 응답 시간 (latency)
- 토큰 사용량 (input/output)
- 검색된 문서 수
- 에러 발생 건수

---

## 🎯 Phase 1 완료 체크리스트

- [ ] 프로젝트 구조 생성 완료
- [ ] OpenSearch 연결 테스트 성공
- [ ] LLM 호출 테스트 성공
- [ ] 기본 RAG 파이프라인 동작 확인
- [ ] 질문셋 30개 이상 준비 완료
- [ ] 전체 질문셋 실행 및 결과 파일 생성

**다음 단계**: PLAN 2 - Strands Agent 모드 추가
