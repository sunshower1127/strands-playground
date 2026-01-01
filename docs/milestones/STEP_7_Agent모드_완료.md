# STEP 7: Strands Agent 모드 추가

## 상태: 완료 ✅

## 목표
Strands Agent를 사용한 자율적 RAG 파이프라인 구현

---

## 구현

### 할 일

- [x] Strands SDK 설치 및 설정
- [x] LiteLLM 모델 프로바이더 설정 (Vertex AI Claude)
- [x] OpenSearch 검색 도구 (@tool) 구현
- [x] Agent RAG 파이프라인 구현
- [x] 모드 전환 구조 (basic ↔ agent)
- [x] Agent 모드 테스트 실행
- [x] 코드 구조 리팩토링

---

## 1. 패키지 설치

```bash
uv add "strands-agents[litellm]" strands-agents-tools
```

---

## 2. 프로젝트 구조

```
src/
├── __init__.py           # create_service() 헬퍼
├── service.py            # 팩토리 함수
├── types.py              # RAGServiceBase, ServiceResult
├── agent/
│   ├── __init__.py
│   ├── rag_agent.py      # AgentRAG 클래스
│   ├── service.py        # AgentRAGService
│   └── tools/
│       ├── __init__.py
│       └── search.py     # search_documents 도구
├── rag/
│   ├── __init__.py
│   ├── pipeline.py       # RAGPipeline
│   ├── service.py        # RAGService
│   ├── types.py          # RAGResult
│   └── modules/          # 파이프라인 컴포넌트
└── (기존 클라이언트들)
```

---

## 3. 사용법

### 헬퍼 함수 (권장)

```python
from src import create_service

# Basic RAG
service = create_service(mode="basic")
result = service.query("연차 휴가는 며칠인가요?")

# Agent RAG
service = create_service(mode="agent")
result = service.query("연차 휴가는 며칠인가요?")
```

### 직접 사용

```python
# Basic RAG
from src.rag import RAGService
service = RAGService(project_id=334, pipeline="minimal")

# Agent RAG
from src.agent import AgentRAGService
service = AgentRAGService(project_id=334)
```

---

## 4. 공통 인터페이스

```python
# src/types.py
class RAGServiceBase(ABC):
    @abstractmethod
    def query(self, question: str) -> ServiceResult:
        pass

@dataclass
class ServiceResult:
    mode: str           # "basic" | "agent"
    question: str
    answer: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    model: str
    sources: list[dict]      # Basic 모드
    tool_calls: list[dict]   # Agent 모드
    timings: dict[str, float] # Basic 모드
```

---

## 5. 검색 도구 (`src/agent/tools/search.py`)

```python
from strands import tool

@tool
def search_documents(query: str, k: int = 5, project_id: int = 334) -> str:
    """OpenSearch에서 관련 문서를 검색합니다."""
    # 임베딩 생성 → KNN 검색 → 결과 포맷팅
    ...
```

---

## 6. Agent 시스템 프롬프트

```python
AGENT_SYSTEM_PROMPT = """당신은 문서 검색 및 질문 답변 전문가입니다.

사용자의 질문에 답하기 위해 다음 도구를 사용할 수 있습니다:
- search_documents: 관련 문서 검색

답변 가이드라인:
1. 먼저 질문을 분석하여 필요한 정보를 파악하세요
2. search_documents 도구로 관련 문서를 검색하세요
3. 검색 결과가 불충분하면 다른 키워드로 재검색하세요
4. 검색된 문서를 바탕으로 정확하게 답변하세요
5. 문서에 없는 내용은 추측하지 마세요
6. 답변할 때 근거가 된 문서를 언급하세요
"""
```

---

## 7. LiteLLM 설정 (Vertex AI)

```python
from strands.models.litellm import LiteLLMModel

model = LiteLLMModel(
    model_id="vertex_ai/claude-sonnet-4-5@20250929",
    params={
        "vertex_project": os.getenv("GCP_PROJECT_ID"),
        "vertex_location": os.getenv("GCP_REGION", "us-east5"),
        "max_tokens": 1024,
    },
)
```

---

## 8. 테스트 결과

### Basic vs Agent 비교

| 항목 | Basic | Agent |
|------|-------|-------|
| 레이턴시 | ~8,600ms | ~15,000ms |
| 검색 방식 | 고정 1회 | 자율적 (1~4회) |
| 소스 | 5개 반환 | 도구 호출 정보 |
| 특징 | 예측 가능 | 유연한 탐색 |

### 테스트 명령어

```bash
# Agent 단독 테스트
uv run python scripts/test_agent.py
uv run python scripts/test_agent.py "출장비 정산은 어떻게 하나요?"

# 통합 테스트
uv run python -c "
from src import create_service
service = create_service(mode='agent')
result = service.query('연차 휴가는 며칠인가요?')
print(result.answer)
"
```

---

## 9. 파일 목록

| 파일 | 설명 |
|------|------|
| `src/types.py` | 공통 인터페이스 (RAGServiceBase, ServiceResult) |
| `src/service.py` | create_service() 팩토리 함수 |
| `src/agent/rag_agent.py` | AgentRAG 클래스 |
| `src/agent/service.py` | AgentRAGService (인터페이스 구현) |
| `src/agent/tools/search.py` | search_documents 도구 |
| `src/rag/service.py` | RAGService (인터페이스 구현) |
| `scripts/test_agent.py` | Agent 테스트 스크립트 |

---

## 향후 개선

### Context Awareness Gate (CAG)

"이 질문에 외부 컨텍스트가 필요한가?"를 먼저 판단.

```
질문 ──► CAG 판단 ──┬── 필요함 ──► RAG 파이프라인 ──► 답변
                   │
                   └── 불필요 ──► LLM 직접 답변
```

Agent 모드에서는 도구 호출 여부를 스스로 판단하므로 CAG가 암묵적으로 적용됨.

### Dynamic Context Selection

쿼리 특성에 따라 검색 결과 개수(k)나 포맷을 동적으로 결정.

### 참고 자료

- [Strands Agents 문서](https://strandsagents.com/latest/)
- [LiteLLM Vertex AI](https://docs.litellm.ai/docs/providers/vertex_partner)
- [Context Awareness Gate (arXiv)](https://arxiv.org/html/2411.16133)
- [Dynamic Context Selection (arXiv)](https://arxiv.org/html/2512.14313)
