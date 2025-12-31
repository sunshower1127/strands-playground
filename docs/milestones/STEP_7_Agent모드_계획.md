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

---

## 8. 향후 개선: Context Awareness Gate (CAG)

### 개요
"이 질문에 외부 컨텍스트가 필요한가?"를 먼저 판단.

```
질문 ──► CAG 판단 ──┬── 필요함 ──► RAG 파이프라인 ──► 답변
                   │
                   └── 불필요 ──► LLM 직접 답변
```

### 장점
- LLM 기본 지식으로 충분한 질문은 검색 생략
- 레이턴시 및 비용 절감

### 단점
- 판단 오류 시 hallucination 위험
- 기업 내부 문서 RAG에서는 대부분 검색 필요

### Agent 모드에서의 활용
Agent가 도구 호출 여부를 스스로 판단하므로, CAG가 암묵적으로 적용됨.
명시적 CAG는 Basic 모드에서 더 유용할 수 있음.

### 도입 시점
- 일반 지식 질문과 도메인 질문이 혼재할 때
- 검색이 불필요한 질문이 상당수일 때

### 참고 자료
- [Context Awareness Gate for RAG (arXiv)](https://arxiv.org/html/2411.16133)

---

## 9. 향후 개선: Dynamic Context Selection

### 개요
쿼리 특성에 따라 검색 결과 개수(k)나 포맷을 동적으로 결정.

```python
# Agent에서 k값을 동적으로 결정
@tool
def search_documents(query: str, complexity: str = "normal") -> str:
    k = {"simple": 3, "normal": 5, "complex": 10}.get(complexity, 5)
    # ...
```

### 2025 연구: DynamicRAG
- 고정 k 대신 **동적으로 문서 수 결정**
- Reranking 필요 여부도 동적 판단

### 현실적 대안
```python
def select_k_simple(query: str) -> int:
    # Rule-based: LLM 호출 없이
    if "비교" in query or "차이" in query:
        return 7  # 비교 질문은 더 많이
    if len(query) < 20:
        return 3  # 짧은 질문은 적게
    return 5
```

### 참고 자료
- [Dynamic Context Selection for RAG (arXiv)](https://arxiv.org/html/2512.14313)
- [Adaptive-RAG Framework](https://arxiv.org/html/2506.00054v1)
