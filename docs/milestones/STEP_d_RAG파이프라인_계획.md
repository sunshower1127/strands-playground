# STEP D: 기본 RAG 파이프라인 구현

## 상태: 계획

## 할 일
- [ ] LLM 클라이언트 구현 (LiteLLM + Vertex AI Claude)
- [ ] 기본 RAG 파이프라인 클래스 구현
- [ ] 테스트 실행 스크립트 작성
- [ ] 결과 파일 포맷 정의
- [ ] 전체 질문셋 실행 및 결과 저장

---

## 1. LLM 호출 로직

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

## 2. 기본 RAG 파이프라인

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

## 3. 테스트 실행 스크립트

```python
# scripts/run_basic.py
def main():
    rag = BasicRAG(...)
    questions = load_questions("data/questions/question_set.json")
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

## 4. 결과 파일 포맷

```json
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
    }
  ],
  "summary": {
    "total_questions": 18,
    "avg_latency_ms": 1500,
    "total_tokens": 28000
  }
}
```

## 5. 성능 지표
- 응답 시간 (latency)
- 토큰 사용량 (input/output)
- 검색된 문서 수
- 에러 발생 건수
