# PLAN 2: Strands Agent 모드 추가

## 2.1 Strands SDK 설정

### 패키지 설치
```bash
pip install strands-agents strands-agents-tools
```

pyproject.toml에 추가:
```toml
dependencies = [
    # ... 기존 의존성
    "strands-agents",
    "strands-agents-tools",
]
```

### LiteLLM 모델 프로바이더 설정
```python
# src/config.py
from strands import Agent
from strands.models import LiteLLMModel

def create_agent_model():
    """Vertex AI Claude를 LiteLLM으로 연결"""
    return LiteLLMModel(
        model_id="vertex_ai/claude-3-sonnet",
        vertex_project=os.getenv("VERTEX_PROJECT"),
        vertex_location=os.getenv("VERTEX_LOCATION"),
    )
```

### 기본 Agent 동작 확인
```python
# 간단한 테스트
from strands import Agent
from strands.models import LiteLLMModel

model = create_agent_model()
agent = Agent(model=model)
response = agent("안녕하세요, 테스트입니다.")
print(response)
```
- LiteLLM → Vertex AI 연결 확인
- 기본 대화 동작 확인

---

## 2.2 RAG Agent 구현

### OpenSearch 검색 도구
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

    # 문서를 텍스트로 포맷팅
    result = []
    for i, doc in enumerate(docs, 1):
        result.append(f"[문서 {i}]\n{doc.content}\n")

    return "\n".join(result)
```

### 추가 도구 (선택적)
```python
@tool
def search_by_metadata(category: str, date_range: str = None) -> str:
    """특정 카테고리나 날짜 범위로 문서 필터링"""
    pass

@tool
def get_document_detail(doc_id: str) -> str:
    """특정 문서의 전체 내용 조회"""
    pass
```

### Agent 프롬프트 설계
```python
# src/rag/agent.py
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

답변 형식:
- 명확하고 구조화된 답변
- 필요시 출처 문서 언급
"""
```

### Agent RAG 파이프라인
```python
# src/rag/agent.py
from strands import Agent
from src.tools.search import search_documents
from src.config import create_agent_model

class AgentRAG:
    def __init__(self):
        self.model = create_agent_model()
        self.agent = Agent(
            model=self.model,
            system_prompt=AGENT_SYSTEM_PROMPT,
            tools=[search_documents],
        )

    def query(self, question: str) -> AgentRAGResult:
        # Agent 실행 및 trajectory 수집
        start = time.time()

        response = self.agent(question)

        elapsed = time.time() - start

        return AgentRAGResult(
            question=question,
            answer=response.content,
            tool_calls=response.tool_calls,  # 도구 호출 기록
            trajectory=response.trajectory,   # 실행 경로
            latency_ms=elapsed * 1000,
            tokens_used=response.usage.total_tokens,
        )
```

### 모드 전환 구조
```python
# src/rag/service.py
from src.rag.basic import BasicRAG
from src.rag.agent import AgentRAG

class RAGService:
    def __init__(self):
        self.basic = BasicRAG()
        self.agent = AgentRAG()

    def query(self, question: str, mode: str = "basic") -> RAGResult:
        """
        Args:
            question: 질문
            mode: "basic" 또는 "agent"
        """
        if mode == "basic":
            return self.basic.query(question)
        elif mode == "agent":
            return self.agent.query(question)
        else:
            raise ValueError(f"Unknown mode: {mode}")
```

---

## 2.3 Agent 테스트 연동

### Agent 모드 실행 스크립트
```python
# scripts/run_agent.py
from src.rag.service import RAGService

def main():
    service = RAGService()
    questions = load_questions("data/questions.json")
    results = []

    for q in questions:
        print(f"Processing: {q['id']} - {q['question'][:50]}...")

        result = service.query(q["question"], mode="agent")

        results.append({
            "id": q["id"],
            "question": q["question"],
            "answer": result.answer,
            "tool_calls": [
                {"name": tc.name, "args": tc.args}
                for tc in result.tool_calls
            ],
            "tool_call_count": len(result.tool_calls),
            "latency_ms": result.latency_ms,
            "tokens_used": result.tokens_used,
        })

    save_results(results, "data/results/agent_results.json")
```

### 결과 파일 포맷 (Agent 확장)
```json
// data/results/agent_results.json
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
        {"name": "search_documents", "args": {"query": "...", "k": 5}},
        {"name": "search_documents", "args": {"query": "...", "k": 3}}
      ],
      "tool_call_count": 2,
      "latency_ms": 3500,
      "tokens_used": 1200
    },
    ...
  ],
  "summary": {
    "total_questions": 50,
    "avg_latency_ms": 3200,
    "avg_tool_calls": 1.8,
    "total_tokens": 58000
  }
}
```

### Agent 특화 지표
| 지표 | 설명 | 측정 방법 |
|------|------|----------|
| tool_call_count | 도구 호출 횟수 | response.tool_calls 길이 |
| search_queries | 실제 검색 쿼리들 | tool_calls에서 추출 |
| retry_count | 재검색 횟수 | 동일 도구 연속 호출 |
| trajectory | 실행 경로 | 도구 호출 순서 |

---

## 🎯 Phase 2 완료 체크리스트

- [ ] Strands SDK 설치 및 import 확인
- [ ] LiteLLM → Vertex AI 연결 테스트
- [ ] search_documents 도구 단독 테스트
- [ ] Agent 기본 동작 확인 (도구 호출 포함)
- [ ] AgentRAG 클래스 구현 완료
- [ ] 모드 전환 (basic ↔ agent) 동작 확인
- [ ] 전체 질문셋 Agent 모드 실행
- [ ] Agent 결과 파일 생성 (tool_calls 포함)

**다음 단계**: PLAN 3 - 비교 평가 및 튜닝
