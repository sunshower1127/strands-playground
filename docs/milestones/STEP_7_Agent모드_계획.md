# STEP E: Strands Agent 모드 추가

## 상태: 계획

## 할 일
- [ ] Strands SDK 설치 및 설정
- [ ] LiteLLM 모델 프로바이더 설정
- [ ] OpenSearch 검색 도구 (@tool) 구현
- [ ] Agent RAG 파이프라인 구현
- [ ] 모드 전환 구조 (basic ↔ agent)
- [ ] Agent 모드 테스트 실행

---

## 1. Strands SDK 설정

### 패키지 설치
```bash
uv add strands-agents strands-agents-tools
```

### LiteLLM 모델 프로바이더
```python
# src/config.py
from strands import Agent
from strands.models import LiteLLMModel

def create_agent_model():
    return LiteLLMModel(
        model_id="vertex_ai/claude-3-sonnet",
        vertex_project=os.getenv("VERTEX_PROJECT"),
        vertex_location=os.getenv("VERTEX_LOCATION"),
    )
```

## 2. OpenSearch 검색 도구

```python
# src/tools/search.py
from strands import tool
from src.opensearch_client import OpenSearchClient

@tool
def search_documents(query: str, k: int = 5) -> str:
    """
    OpenSearch에서 관련 문서를 검색합니다.

    Args:
        query: 검색할 질문 또는 키워드
        k: 반환할 문서 개수 (기본값: 5)

    Returns:
        검색된 문서들의 내용
    """
    client = OpenSearchClient.get_instance()
    docs = client.search(query, k=k)

    result = []
    for i, doc in enumerate(docs, 1):
        result.append(f"[문서 {i}]\n{doc.content}\n")

    return "\n".join(result)
```

## 3. Agent 프롬프트

```python
AGENT_SYSTEM_PROMPT = """
당신은 문서 검색 및 질문 답변 전문가입니다.

사용자의 질문에 답하기 위해 다음 도구를 사용할 수 있습니다:
- search_documents: 관련 문서 검색

답변 가이드라인:
1. 먼저 질문을 분석하여 필요한 정보를 파악하세요
2. search_documents 도구로 관련 문서를 검색하세요
3. 검색 결과가 불충분하면 다른 키워드로 재검색하세요
4. 검색된 문서를 바탕으로 정확하게 답변하세요
5. 문서에 없는 내용은 추측하지 마세요
"""
```

## 4. Agent RAG 파이프라인

```python
# src/rag/agent.py
class AgentRAG:
    def __init__(self):
        self.model = create_agent_model()
        self.agent = Agent(
            model=self.model,
            system_prompt=AGENT_SYSTEM_PROMPT,
            tools=[search_documents],
        )

    def query(self, question: str) -> AgentRAGResult:
        start = time.time()
        response = self.agent(question)
        elapsed = time.time() - start

        return AgentRAGResult(
            question=question,
            answer=response.content,
            tool_calls=response.tool_calls,
            trajectory=response.trajectory,
            latency_ms=elapsed * 1000,
            tokens_used=response.usage.total_tokens,
        )
```

## 5. 모드 전환 구조

```python
# src/rag/service.py
class RAGService:
    def __init__(self):
        self.basic = BasicRAG()
        self.agent = AgentRAG()

    def query(self, question: str, mode: str = "basic") -> RAGResult:
        if mode == "basic":
            return self.basic.query(question)
        elif mode == "agent":
            return self.agent.query(question)
```

## 6. Agent 결과 포맷

```json
{
  "run_id": "agent_20241230_150000",
  "config": {
    "model": "claude-3-sonnet",
    "mode": "agent",
    "tools": ["search_documents"]
  },
  "results": [
    {
      "id": 1,
      "question": "...",
      "answer": "...",
      "tool_calls": [
        {"name": "search_documents", "args": {"query": "...", "k": 5}}
      ],
      "tool_call_count": 2,
      "latency_ms": 3500,
      "tokens_used": 1200
    }
  ]
}
```

## 7. Agent 특화 지표

| 지표 | 설명 |
|------|------|
| tool_call_count | 도구 호출 횟수 |
| search_queries | 실제 검색 쿼리들 |
| retry_count | 재검색 횟수 |
| trajectory | 실행 경로 |
