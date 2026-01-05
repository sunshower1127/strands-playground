# STEP 11: Agent 구체화 계획

## 목표
Strands Agent 기반 RAG 시스템을 ChatGPT 스타일의 통합 아키텍처로 발전시키기

---

## 1. 아키텍처 설계

### 1.1 통합 Agent 방식 (ChatGPT 스타일)

```
모든 대화 → 단일 Agent (동일 세션)
              │
              ├─ 일반 모드: Haiku + 도구 없음 (저렴)
              │
              └─ Agent 모드: Sonnet + 전체 도구 (고급)
```

**핵심 원칙:**
- 세션은 공유, 모델/도구만 전환
- 모드 전환해도 컨텍스트 유지
- `/agent` 명령어 또는 UI 토글로 전환

### 1.2 모드별 구성

| 모드 | 모델 | 도구 | 프롬프트 | 용도 |
|------|------|------|----------|------|
| 일반 | Haiku | 없음 | 간단 | 일반 QA, 잡담 |
| Agent | Sonnet | search, ask_user | 상세 | 복잡한 검색, 추론 |

---

## 2. 세션 및 컨텍스트 관리

### 2.1 Strands 컴포넌트

```python
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.session.file_session_manager import FileSessionManager

# 세션 관리 (대화 히스토리 저장/복원)
session_manager = FileSessionManager(
    session_id=user_session_id,
    storage_dir="./sessions",
)

# 컨텍스트 관리 (토큰 한계 대응)
conversation_manager = SlidingWindowConversationManager(
    window_size=20,
    should_truncate_results=True,
)
```

### 2.2 컨텍스트 관리 전략

**JetBrains Research 2025 결론:**
- Sliding Window가 Summarization보다 52% 저렴, 성능도 우수
- "Simplicity often takes the prize"

**권장 방식:**
1. 기본: SlidingWindowConversationManager
2. 필요 시: SummarizingConversationManager (하이브리드)

### 2.3 컨텍스트 노출

- 유저에게 퍼센티지 노출 **안함** (복잡도 증가)
- 대신 **"새 대화" 버튼** 제공
- 대화가 길어지면 Agent가 자연스럽게 "다시 말씀해주세요"

---

## 3. Interrupt 시스템 (Human-in-the-Loop)

### 3.1 Interrupt 트리거 방식

**개발자가 코드로 정의** (LLM 자율 판단 아님)

```python
@tool
def search_documents(query: str, tool_context) -> str:
    results = hybrid_search(query)

    # 결과 0개면 interrupt (결정적 조건)
    if len(results) == 0:
        tool_context.interrupt("no_results", reason={
            "message": f"'{query}'로 검색했지만 결과가 없습니다.",
            "suggestion": "다른 검색어를 제안해주세요."
        })

    return format_results(results)
```

### 3.2 ask_user 도구 (LLM 판단 + Interrupt)

```python
@tool
def ask_user(question: str, tool_context) -> str:
    """사용자에게 명확화 질문을 합니다."""
    tool_context.interrupt("clarify", reason={"question": question})
```

LLM이 ask_user 호출 → 자동 interrupt → 유저 입력 대기

### 3.3 Interrupt 처리 루프

```python
result = agent(question)

while result.stop_reason == "interrupt":
    responses = []
    for interrupt in result.interrupts:
        user_input = get_user_input(interrupt.reason)
        responses.append({
            "interruptResponse": {
                "interruptId": interrupt.id,
                "response": user_input
            }
        })
    result = agent(responses)
```

---

## 4. 구현 설계

### 4.1 UnifiedAgent 클래스

```python
class UnifiedAgent:
    def __init__(self, session_id: str, project_id: int = 334):
        self.session_manager = FileSessionManager(
            session_id=session_id,
            storage_dir="./sessions",
        )
        self.conversation_manager = SlidingWindowConversationManager(
            window_size=20,
            should_truncate_results=True,
        )
        self.project_id = project_id

    def query(self, question: str, mode: str = "normal") -> AgentResult:
        if mode == "normal":
            model = LiteLLMModel(model_id="vertex_ai/claude-haiku")
            tools = []
            prompt = SIMPLE_PROMPT
        else:  # "agent"
            model = LiteLLMModel(model_id="vertex_ai/claude-sonnet-4-5")
            tools = [search_documents, ask_user]
            prompt = AGENT_PROMPT

        agent = Agent(
            model=model,
            session_manager=self.session_manager,
            conversation_manager=self.conversation_manager,
            tools=tools,
            system_prompt=prompt,
        )

        return self._handle_interrupts(agent, question)

    def _handle_interrupts(self, agent, question):
        result = agent(question)
        # interrupt 처리 로직...
        return result
```

### 4.2 API 인터페이스

```python
# POST /chat
{
    "session_id": "user-123-conv-456",
    "question": "연차 휴가 규정 알려줘",
    "mode": "agent"  # or "normal"
}

# Response
{
    "answer": "...",
    "sources": [...],
    "interrupt": null,  # or {"type": "clarify", "question": "..."}
    "tokens": {"input": 1234, "output": 567}
}
```

---

## 5. 테스트 전략

### 5.1 테스트 레벨

| 레벨 | 대상 | 방법 | 자동화 |
|------|------|------|--------|
| Unit | search_documents 도구 | pytest | ✅ |
| Integration | Session 저장/복원 | Mock SessionManager | ✅ |
| E2E (결정적) | Interrupt 시나리오 | 고정 조건 (결과 0개) | ✅ |
| E2E (비결정적) | LLM 답변 품질 | 골든 테스트 | ⚠️ |

### 5.2 골든 테스트 (스냅샷 기반)

```python
def test_golden_scenario():
    result = run_scenario("해외출장_문의")

    # 첫 실행: 수동 검증 후 저장
    # 이후: 스냅샷 비교
    assert result == load_golden("해외출장_문의.json")
```

### 5.3 Session 테스트 (Mock)

```python
def test_session_continuity():
    mock = MockSessionManager([
        {"role": "user", "content": "내 이름은 철수야"},
        {"role": "assistant", "content": "안녕하세요 철수님"},
    ])
    agent = Agent(session_manager=mock)
    result = agent("내 이름이 뭐였지?")
    assert "철수" in result.answer
```

---

## 6. 수정 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/agent/unified_agent.py` | 신규 - 통합 Agent 클래스 |
| `src/agent/tools/search.py` | Interrupt 로직 추가 |
| `src/agent/tools/ask_user.py` | 신규 - 유저 질문 도구 |
| `src/agent/prompts.py` | 모드별 프롬프트 분리 |
| `tests/agent/test_session.py` | 신규 - 세션 테스트 |
| `tests/agent/test_golden.py` | 신규 - 골든 테스트 |

---

## 7. 참고 자료

### 7.1 ChatGPT Agent Mode (2025.07)
- Tools 드롭다운으로 모드 전환
- 같은 대화 내 컨텍스트 유지
- Agent 모드에서 long-term memory 제한 (보안)

### 7.2 JetBrains Research (2025.12)
- Sliding Window > Summarization (비용 52% 절감)
- 하이브리드 권장: Sliding 기본 + 임계치 도달 시 Summarization

### 7.3 Strands 공식 문서
- [Context Management](https://strandsagents.com/latest/user-guide/concepts/agents/context-management/)
- [Conversation Management](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/conversation-management/)
- [Interrupt System](https://strandsagents.com/latest/user-guide/concepts/agents/interrupts/)

---

## 8. 도구 호출 횟수 제한 (토큰 절약)

### 8.1 제한 필요성

- 기본 검색 에이전트는 도구 호출을 최소화하여 토큰 비용 절감
- 무한 루프 방지 및 응답 시간 개선

### 8.2 제한 방법

#### 방법 1: `max_turns` 파라미터 (권장)

```python
from strands import Agent

# 기본 검색용 - 턴 제한으로 간접 제어
basic_agent = Agent(
    model=model,
    tools=[search_documents],
    max_turns=3,  # 최대 3턴으로 제한
)

# 복잡한 작업용 - 더 많은 턴 허용
advanced_agent = Agent(
    model=model,
    tools=[search_documents, ask_user, analyze],
    max_turns=10,
)
```

> **참고:** Strands SDK에는 `max_tool_calls` 같은 직접적인 파라미터가 없음. `max_turns`로 간접 제어.

#### 방법 2: 도구 내 직접 카운팅

```python
call_counts = {}

@tool
def search_documents(query: str) -> str:
    """문서를 검색합니다."""
    # 호출 횟수 추적
    call_counts['search'] = call_counts.get('search', 0) + 1

    if call_counts['search'] > 3:
        return "검색 횟수 제한 초과 (최대 3회). 기존 결과로 답변해주세요."

    return hybrid_search(query)
```

#### 방법 3: 시스템 프롬프트로 유도

```python
EFFICIENT_SEARCH_PROMPT = """
검색 작업 시 다음 원칙을 따르세요:
- 최대 2-3번의 검색만 수행
- 첫 검색 결과로 충분하면 추가 검색 금지
- 검색어를 신중하게 선택하여 한 번에 원하는 결과 획득
"""
```

### 8.3 모드별 권장 설정

| 모드 | max_turns | 도구 제한 전략 | 예상 토큰 |
|------|-----------|----------------|-----------|
| 일반 (Haiku) | N/A | 도구 없음 | 최소 |
| 기본 검색 | 2-3 | 프롬프트 유도 | 중간 |
| 고급 Agent | 5-10 | 제한 없음 | 높음 |

### 8.4 UnifiedAgent에 적용

```python
class UnifiedAgent:
    def query(self, question: str, mode: str = "normal") -> AgentResult:
        if mode == "normal":
            model = LiteLLMModel(model_id="vertex_ai/claude-haiku")
            tools = []
            max_turns = None
        elif mode == "basic_search":
            model = LiteLLMModel(model_id="vertex_ai/claude-haiku")
            tools = [search_documents]
            max_turns = 3  # 토큰 절약
        else:  # "agent"
            model = LiteLLMModel(model_id="vertex_ai/claude-sonnet-4-5")
            tools = [search_documents, ask_user]
            max_turns = 10  # 복잡한 작업 허용

        agent = Agent(
            model=model,
            tools=tools,
            max_turns=max_turns,
            # ...
        )
```

---

## 9. 실시간 이벤트 및 중단 기능

### 9.1 Callback Handlers (도구 호출 UI 표시)

Strands SDK는 에이전트 실행 중 이벤트를 실시간으로 받을 수 있는 **Callback Handler**를 제공합니다.

```python
from strands import Agent

def ui_callback_handler(**kwargs):
    # 도구 호출 감지 → UI에 "검색 중..." 표시
    if "current_tool_use" in kwargs and kwargs["current_tool_use"].get("name"):
        tool_name = kwargs["current_tool_use"]["name"]
        print(f"🔧 도구 사용 중: {tool_name}")
        # 여기서 웹소켓으로 프론트엔드에 상태 전송 가능
        # await websocket.send({"status": "tool_call", "tool": tool_name})

    # 이벤트 루프 시작
    if kwargs.get("start_event_loop", False):
        print("▶️ 처리 시작...")

    # 완료
    if kwargs.get("complete", False):
        print("✅ 완료")

agent = Agent(
    model=model,
    tools=[search_documents],
    callback_handler=ui_callback_handler,  # 콜백 등록
)
```

**주요 이벤트:**
| 이벤트 | 설명 |
|--------|------|
| `current_tool_use` | 도구 호출 시작 (도구명 포함) |
| `init_event_loop` | 이벤트 루프 초기화 |
| `start_event_loop` | 사이클 시작 |
| `complete` | 사이클 완료 |

> **참고:** Callback Handler는 Python만 지원. TypeScript는 async iterator 사용.

### 9.2 도구 호출 취소 (Hooks)

`BeforeToolCallEvent` 훅을 사용해 도구 호출을 취소할 수 있습니다.

```python
from strands.hooks import Hook

class ApprovalHook(Hook):
    def on_before_tool_call(self, event):
        # 특정 조건에서 도구 호출 취소
        if should_cancel():
            event.cancel_tool = "사용자가 취소했습니다"
            return

        # 또는 사용자 확인 요청
        if event.tool_name == "delete_document":
            if not get_user_approval(f"{event.tool_name} 실행을 허용하시겠습니까?"):
                event.cancel_tool = "사용자가 거부했습니다"
```

### 9.3 Force Stop (강제 중단)

에이전트 실행을 강제로 중단할 수 있습니다.

```python
async for event in agent.stream_async(question):
    # 강제 중단 감지
    if event.get("force_stop", False):
        reason = event.get("force_stop_reason", "unknown")
        print(f"⛔ 강제 중단: {reason}")
        break

    # 사용자가 취소 버튼 클릭 시
    if user_clicked_cancel:
        # agent 중단 로직 (구현 방식은 SDK 버전에 따라 다름)
        break
```

### 9.4 UI 통합 예시

```python
class AgentWithUI:
    def __init__(self, websocket):
        self.ws = websocket

    def create_callback(self):
        async def callback(**kwargs):
            if "current_tool_use" in kwargs:
                tool = kwargs["current_tool_use"].get("name")
                if tool:
                    await self.ws.send_json({
                        "type": "status",
                        "message": f"{tool} 실행 중...",
                        "tool": tool
                    })

            if kwargs.get("complete"):
                await self.ws.send_json({
                    "type": "status",
                    "message": "완료",
                    "done": True
                })

        return callback
```

### 9.5 참고 문서

- [Callback Handlers](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/streaming/callback-handlers/)
- [Async Iterators](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/streaming/async-iterators/)

---

## 10. 마일스톤

- [ ] Phase 1: UnifiedAgent 기본 구조 구현
- [ ] Phase 2: Interrupt + ask_user 도구 추가
- [ ] Phase 3: Session 저장/복원 구현
- [ ] Phase 4: 테스트 코드 작성 (Unit, Golden)
- [ ] Phase 5: API 통합 및 검증

---

## 9. 향후 발전: Multi-Agent (Swarm)

현재는 단일 Agent + 여러 도구 구조로 충분하지만, 향후 복잡한 요구사항에 대비해 Swarm 패턴을 검토.

### 9.1 현재 vs Swarm 비교

| 항목 | 현재 (단일 Agent + 도구) | Swarm (Multi-Agent) |
|------|------------------------|---------------------|
| 구조 | 1 Agent + N 도구 | N Agent (각자 LLM 보유) |
| 판단 주체 | 1개 LLM이 모든 판단 | 각 Agent가 자율 판단 |
| 통신 방식 | 도구 호출 → 결과 반환 | Agent 간 handoff (위임) |
| 비용 | LLM 1회 호출 | LLM N회 호출 |
| 복잡도 | 낮음 | 높음 |

### 9.2 핵심 차이: 자율성

```python
# 단일 Agent + LLM 도구 (현재)
@tool
def summarize(text: str) -> str:
    return llm.generate(f"요약해줘: {text}")  # 시키는 것만 수행

# Swarm Agent
class ResearchAgent:
    def run(self, task):
        # 스스로 판단해서 다른 Agent 호출 가능
        if self.need_more_info():
            return handoff(SearchAgent, new_task)  # 자율적 위임
        return self.complete(task)
```

**도구 안에 LLM이 있어도 Swarm이 아님** - 자율성 + Agent 간 통신이 있어야 Swarm.

### 9.3 Swarm이 필요한 시점

| 상황 | 단일 Agent | Swarm |
|------|-----------|-------|
| 내부 문서 검색 + 웹 검색 조합 | ✅ 충분 | 불필요 |
| 논문 10개 각각 요약 후 종합 | △ 가능하지만 복잡 | ✅ 적합 |
| 코딩(Claude) + 검색(Gemini) 혼용 | ❌ 어려움 | ✅ 적합 |
| 장시간 자율 작업 (Deep Research) | ❌ 한계 | ✅ 적합 |

### 9.4 관련 프레임워크

| 프레임워크 | 특징 |
|-----------|------|
| **OpenAI Swarm** | OpenAI 실험적 멀티 에이전트 |
| **LangGraph** | 에이전트 워크플로우 그래프 정의 |
| **CrewAI** | 역할 기반 멀티 에이전트 협업 |
| **AutoGen** | Microsoft의 대화형 멀티 에이전트 |

### 9.5 현재 프로젝트 결론

**당분간 단일 Agent + 도구로 충분**
- Level 4 질문 (내부 문서 + 웹 검색 조합)은 도구 2개로 해결
- Swarm 도입은 오버엔지니어링
- 추후 Deep Research 같은 복잡한 요구사항 발생 시 재검토

---

## 10. LLM 모델 가격 비교 및 선택 가이드

### 10.1 저가 모델 비교 (100만 토큰 기준, 2025년)

#### 주요 저가 모델

| 모델 | Input | Output | 특징 |
|------|-------|--------|------|
| **Gemini 1.5 Flash-8B** | $0.0375 | - | Google, 가장 저렴 |
| **GPT-4o mini** | $0.15 | $0.60 | OpenAI 생태계, 균형 |
| **Claude 3 Haiku** | $0.25 | $1.25 | 빠른 응답, 고객지원 적합 |
| **Claude 3.5 Haiku** | $0.80 | $4.00 | 코딩/에이전트 강점 |
| **Grok 4.1 Fast** | $0.20 | $0.50 | xAI, 2M 컨텍스트, 가성비 |
| **Grok 3 Mini** | $0.30 | $0.50 | xAI 경량 모델 |

#### 중국 모델 (압도적 가격 경쟁력)

| 모델 | Input | Output | 비고 |
|------|-------|--------|------|
| **DeepSeek V3.2-Exp** (cache hit) | **$0.028** | $0.42 | 현존 최저가 |
| **DeepSeek V3.2-Exp** (cache miss) | $0.28 | $0.42 | - |
| **DeepSeek Chat** | $0.56 | $1.68 | 일반 채팅용 |
| **Qwen 2.5-Max** | $0.38 | ~$0.38 | MoE 아키텍처 |

> **참고**: DeepSeek는 GPT-5 대비 10~30배 저렴. 중국 오픈소스 모델이 전 세계 AI 사용량의 약 30% 차지 (a16z 연구)

#### Meta Llama (오픈소스, 호스팅 업체별)

| 업체 | 모델 | Input | Output |
|------|------|-------|--------|
| **DeepInfra** | Llama 3.1 8B | **$0.03** | **$0.05** |
| **Cerebras** | Llama 3.1 8B | $0.10 | - |
| **Groq** | Llama 3.3 70B | $0.59 | $0.79 |
| **Together.ai** | Llama 계열 | $0.20~$0.49 | - |

### 10.2 Google Vertex AI 지원 현황

| 모델 | Vertex AI 지원 | 비고 |
|------|:-------------:|------|
| **Gemini** (Google) | ✅ 완전 지원 | 네이티브, Flash/Pro 전체 |
| **Claude** (Anthropic) | ✅ 지원 | Opus 4.5, Sonnet 3.7, Haiku 4.5 |
| **Llama** (Meta) | ✅ 지원 | Llama 4 Scout, 3.1 등 |
| **DeepSeek** | ✅ 지원 | V3.2, V3.1, R1 (0528), OCR |
| **Mistral** | ✅ 지원 | Codestral, Small 3.1, Mixtral 8x7B |
| **Qwen** (Alibaba) | ❓ 미확인 | 직접 확인 필요 |
| **Grok** (xAI) | ❌ 미지원 | xAI 자체 API만 제공 |
| **GPT** (OpenAI) | ❌ 미지원 | OpenAI API 직접 사용 |

**Vertex AI 장점:**
- 통합 빌링 (GCP 청구서)
- VPC 내 배포 (보안)
- 엔터프라이즈 SLA/컴플라이언스

### 10.3 Agent용 모델 선택 전략

#### 고가 모델 (복잡한 추론/의사결정)

| 모델 | 가격 (1M tokens) | 용도 |
|------|------------------|------|
| **Claude 4 Opus** | $15 / $75 | 코딩, 복잡한 에이전트 |
| **OpenAI o3** | 고가 | 수학적 추론, 단계별 사고 |
| **GPT-5** | $1.25 / $10 | 자동 라우팅, 멀티모달 |
| **Claude Sonnet 4.5** | $3 / $15 | 장시간 복잡 태스크 |

#### 저가 모델 (단순 작업/라우팅)

| 모델 | 가격 (1M tokens) | 용도 |
|------|------------------|------|
| **GPT-4o mini** | $0.15 / $0.60 | 초기 처리, 분류 |
| **Claude Haiku** | $0.80 / $4 | 빠른 응답, 간단한 작업 |
| **Gemini Flash** | $0.0375~ | 대량 처리 |
| **DeepSeek** | $0.028~ | 최저가 |

#### 추천 티어링 전략

```
┌─────────────────────────────────────────────────────┐
│                    User Request                      │
└─────────────────────┬───────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│         Router/Orchestrator (저가 모델)              │
│    GPT-4o mini / Haiku / Gemini Flash               │
│    - 요청 분류                                       │
│    - 복잡도 판단                                     │
│    - 적절한 모델로 라우팅                            │
└─────────────────────┬───────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    ┌─────────┐  ┌─────────┐  ┌─────────┐
    │ 단순작업 │  │ 중간작업 │  │ 복잡작업 │
    │  (70%)  │  │  (20%)  │  │  (10%)  │
    └────┬────┘  └────┬────┘  └────┬────┘
         │            │            │
         ▼            ▼            ▼
    GPT-4o mini   Sonnet 4    Opus 4 / o3
    Haiku        GPT-4o       GPT-5
    Flash
```

> **핵심**: "70%의 일반 작업에 저가 모델, 30%의 복잡한 작업에 고가 모델을 사용하면 전체를 고가 모델로 처리하는 것보다 ROI가 훨씬 높다"

### 10.4 참고 자료

- [LLM API Pricing Comparison 2025 - IntuitionLabs](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)
- [DeepSeek API Pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [xAI Models and Pricing](https://docs.x.ai/docs/models)
- [Groq On-Demand Pricing](https://groq.com/pricing)
- [NVIDIA: Train Small Orchestration Agents](https://developer.nvidia.com/blog/train-small-orchestration-agents-to-solve-big-problems/)
- [GitHub: Which AI model should I use?](https://github.blog/ai-and-ml/github-copilot/which-ai-model-should-i-use-with-github-copilot/)

---

## 11. Strands 멀티 에이전트 오케스트레이션 패턴

Strands 1.0에서 4가지 멀티 에이전트 오케스트레이션 패턴이 도입되었다.

### 11.1 패턴 개요

| 패턴 | 특징 | 제어 주체 | 적합한 상황 |
|------|------|----------|------------|
| **Agents-as-Tools** | 오케스트레이터가 전문가 호출 | 오케스트레이터 LLM | 동적 라우팅, 일반적 멀티 에이전트 |
| **Graph** | 개발자가 흐름 명시적 정의 | 개발자 (코드) | 예측 가능한 워크플로우 |
| **Swarm** | 에이전트 자율 협업 | 에이전트들 자신 | 창의적/탐색적 작업 |
| **Workflow** | 순차적 태스크 파이프라인 | 개발자 (코드) | 단순한 순서 실행 |

### 11.2 Agents-as-Tools (계층적 위임)

**개념**: 전문 에이전트를 "도구"로 변환하여 오케스트레이터가 호출

```python
from strands import Agent
from strands.models import BedrockModel

# 전문 에이전트 정의
search_agent = Agent(
    name="search",
    system_prompt="검색 전문가입니다",
    model=BedrockModel(model_id="anthropic.claude-3-haiku")  # 저가 모델
)

code_agent = Agent(
    name="coder",
    system_prompt="코드 전문가입니다",
    model=BedrockModel(model_id="anthropic.claude-sonnet-4-20250514")  # 고가 모델
)

# 오케스트레이터 (저가 모델로 라우팅)
orchestrator = Agent(
    system_prompt="적절한 전문가에게 작업을 위임하세요",
    tools=[search_agent.as_tool(), code_agent.as_tool()],
    model=BedrockModel(model_id="anthropic.claude-3-haiku")
)
```

**적합한 경우:**
- 동적 라우팅이 필요할 때
- LLM이 상황 판단해서 전문가 선택
- 가장 일반적인 멀티 에이전트 패턴

### 11.3 Graph (구조화된 워크플로우)

**개념**: 에이전트들을 노드로 연결한 "흐름도", 개발자가 명시적으로 정의

```python
from strands import Agent
from strands.multiagent import GraphBuilder

# 에이전트 정의
researcher = Agent(name="researcher", system_prompt="리서치 전문가")
analyst = Agent(name="analyst", system_prompt="분석 전문가")

# 그래프 빌드
builder = GraphBuilder()
builder.add_node(researcher, "researcher")
builder.add_node(analyst, "analyst")
builder.add_edge("researcher", "analyst")  # 연결
builder.set_entry_point("researcher")

graph = builder.build()
result = graph("AI가 의료에 미치는 영향을 조사해줘")
```

**조건부 분기 예시:**

```python
def is_technical(state):
    result = str(state.results.get("classifier").result)
    return "technical" in result.lower()

def is_business(state):
    result = str(state.results.get("classifier").result)
    return "business" in result.lower()

builder = GraphBuilder()
builder.add_node(classifier, "classifier")
builder.add_node(tech_specialist, "tech")
builder.add_node(business_specialist, "biz")

# 조건부 엣지
builder.add_edge("classifier", "tech", condition=is_technical)
builder.add_edge("classifier", "biz", condition=is_business)
```

```
                    ┌─→ [tech_specialist] ─→ [tech_report]
[classifier] ──────┤
                    └─→ [business_specialist] ─→ [biz_report]
```

**피드백 루프 (승인까지 반복):**

```python
def needs_revision(state):
    result = str(state.results.get("reviewer").result)
    return "revision needed" in result.lower()

def is_approved(state):
    result = str(state.results.get("reviewer").result)
    return "approved" in result.lower()

builder = GraphBuilder()
builder.add_node(draft_writer, "writer")
builder.add_node(reviewer, "reviewer")
builder.add_node(publisher, "publisher")

builder.add_edge("writer", "reviewer")
builder.add_edge("reviewer", "writer", condition=needs_revision)  # 되돌아감
builder.add_edge("reviewer", "publisher", condition=is_approved)

# 무한 루프 방지
builder.set_max_node_executions(10)
```

**적합한 경우:**
- 조건부 분기가 필요할 때 (if-else)
- 피드백 루프 (승인까지 반복)
- 병렬 처리 후 합치기
- Human-in-the-loop 승인 게이트
- 예측 가능하고 디버깅 쉬운 워크플로우

### 11.4 Swarm (자율 협업)

**개념**: 에이전트들이 "자율적으로" 서로 일을 넘기면서 협업 (Handoff)

```python
from strands import Agent
from strands.multiagent import Swarm

# 전문 에이전트들 정의
researcher = Agent(name="researcher", system_prompt="리서치 전문가. 조사 후 필요하면 다른 전문가에게 넘겨라")
coder = Agent(name="coder", system_prompt="코딩 전문가. 구현 후 리뷰어에게 넘겨라")
reviewer = Agent(name="reviewer", system_prompt="코드 리뷰 전문가")
architect = Agent(name="architect", system_prompt="아키텍처 전문가")

# Swarm 생성
swarm = Swarm(
    [researcher, coder, reviewer, architect],
    entry_point=researcher,      # 시작점
    max_handoffs=20,             # 최대 핸드오프 횟수
    max_iterations=20,           # 최대 반복
    execution_timeout=900.0,     # 전체 타임아웃 15분
    repetitive_handoff_detection_window=8,   # 반복 감지
    repetitive_handoff_min_unique_agents=3   # 최소 3명이 돌아가며
)

# 실행 - 에이전트들이 알아서 협업
result = swarm("TODO 앱을 위한 REST API를 설계하고 구현해줘")

print(f"거쳐간 에이전트: {[node.node_id for node in result.node_history]}")
# 출력 예: ['researcher', 'architect', 'coder', 'reviewer', 'coder', 'reviewer']
```

**Handoff 흐름:**

```
[researcher] "조사 끝났어, 코드 구현이 필요하네"
     │
     ▼ (자발적 handoff)
[coder] "구현했어, 리뷰 받아야겠다"
     │
     ▼ (자발적 handoff)
[reviewer] "버그 있어, 수정 필요해"
     │
     ▼ (자발적 handoff)
[coder] "수정했어, 다시 리뷰해줘"
     ...
```

**Swarm이 유용한 분야:**

| 분야 | 예시 |
|------|------|
| 창의적 콘텐츠 제작 | 작가 ↔ 편집자 반복 협업 |
| 소프트웨어 개발 | 코드 → 리뷰 → 수정 → 재리뷰 사이클 |
| 복잡한 문제 해결/연구 | 다각도 조사, 여러 전문가 의견 필요 |
| 고객 지원 에스컬레이션 | 자연스러운 담당자 이동 |

**Swarm이 안 맞는 경우:**

| 상황 | 이유 | 대안 |
|------|------|------|
| 단순 분류/라우팅 | 오버킬 | Agents-as-Tools |
| 엄격한 순서 필요 | 예측 어려움 | Graph |
| 비용 민감 | 핸드오프마다 토큰 소모 | Graph/Workflow |
| 감사/로깅 중요 | 흐름 추적 어려움 | Graph |

### 11.5 패턴 비교 요약

| 특성 | Agents-as-Tools | Graph | Swarm |
|------|----------------|-------|-------|
| **제어 주체** | 오케스트레이터 | 개발자 (코드) | 에이전트들 자신 |
| **흐름** | 중앙 집중 | 미리 정의됨 | 자율적 |
| **예측성** | 중간 | 높음 | 낮음 |
| **유연성** | 중간 | 낮음 | 높음 |
| **디버깅** | 쉬움 | 쉬움 | 어려움 |
| **비용** | 중간 | 낮음 | 높음 (핸드오프 비용) |

**한줄 정리:**

| 패턴 | 비유 |
|------|------|
| **Agents-as-Tools** | "팀장이 지시" |
| **Graph** | "매뉴얼대로" |
| **Swarm** | "알아서 협업" |

### 11.6 패턴 조합

Graph 안에 Swarm을 노드로 넣는 것도 가능:

```python
from strands.multiagent import GraphBuilder, Swarm

# 창의팀은 Swarm으로 자유롭게
creative_swarm = Swarm([writer, editor, designer])

# 전체 프로세스는 Graph로 통제
builder = GraphBuilder()
builder.add_node(planner, "plan")
builder.add_node(creative_swarm, "creative")  # Swarm을 노드로!
builder.add_node(reviewer, "review")
builder.add_edge("plan", "creative")
builder.add_edge("creative", "review")
```

### 11.7 단일 Agent vs Agents-as-Tools 선택 기준

Agents-as-Tools가 항상 더 나은 것은 아니다. 상황에 따라 단일 Agent가 더 적합할 수 있다.

#### 언제 뭐가 나은가?

| 상황 | 단일 Agent | Agents-as-Tools |
|------|:----------:|:---------------:|
| 간단한 QA 봇 | ✅ 더 나음 | 오버킬 |
| 작업 유형이 1~2개 | ✅ 더 나음 | 불필요한 복잡도 |
| 트래픽 적음 (월 1000건 이하) | ✅ 더 나음 | 개발비 > 절감액 |
| **작업 복잡도 편차 큼** | △ | ✅ 더 나음 |
| **대량 트래픽** | △ | ✅ 더 나음 |
| **다양한 전문 영역** | △ | ✅ 더 나음 |

#### Agents-as-Tools가 "항상" 더 낫지 않은 이유

**1. 오버헤드 비용**

```
단일 Agent:     [요청] → [LLM 1회 호출] → [응답]

Agents-as-Tools: [요청] → [오케스트레이터] → [전문 Agent] → [응답]
                              ↑                    ↑
                           LLM 호출 1           LLM 호출 2
```

- 라우팅에도 LLM 호출이 필요
- 간단한 작업이면 **오케스트레이터 비용이 오히려 낭비**

**2. 개발/운영 복잡도**

```python
# 단일 Agent - 심플
agent = Agent(model=sonnet, tools=[search, calculate])

# Agents-as-Tools - 관리 포인트 증가
search_agent = Agent(...)
calc_agent = Agent(...)
orchestrator = Agent(tools=[search_agent.as_tool(), calc_agent.as_tool()])
# 프롬프트 3개, 모델 설정 3개, 디버깅 3배...
```

**3. 지연시간 증가**

- 오케스트레이터 → 전문 Agent 순차 호출
- 단순 질문에도 2번 왕복

#### Agents-as-Tools가 확실히 나은 경우

NVIDIA 연구나 엔터프라이즈 사례가 해당되는 조건:

1. **복잡도 편차가 큼**: 70%는 단순, 30%는 복잡
2. **대량 트래픽**: 월 수십만 건 이상 → 저가 모델 비용 절감 효과 큼
3. **전문 영역이 명확히 분리됨**: 검색 vs 코딩 vs 분석 등
4. **비용 민감도 높음**: 토큰 비용이 운영비의 상당 부분

#### 현재 프로젝트 관점

```
현재 상황:
- RAG 시스템 (검색 + 답변 생성)
- 작업 유형: 거의 비슷 (문서 검색 → 답변)
- 트래픽: 초기 단계

→ 단일 Agent + 도구(search, ask_user)로 충분
```

**Agents-as-Tools 도입 시점:**
- 웹 검색 + 내부 검색 + 코드 생성 등 **영역이 분화**될 때
- 트래픽이 늘어 **비용 최적화**가 중요해질 때
- 단순 질문이 많아져 **Haiku로 처리 가능한 비율**이 높아질 때

#### 정리

| | 단일 Agent | Agents-as-Tools |
|---|---|---|
| **장점** | 심플, 낮은 지연, 개발 빠름 | 비용 최적화, 전문화, 확장성 |
| **단점** | 모든 요청에 고가 모델 | 복잡도, 오케스트레이터 오버헤드 |
| **적합** | MVP, 단순 도메인 | 대규모, 다양한 작업 유형 |

> **결론**: AWS/NVIDIA 사례는 **"대규모 + 다양한 작업 유형"** 조건에서의 결과.
> 작은 규모나 단일 도메인에서는 단일 Agent가 더 실용적일 수 있음.

### 11.8 참고 자료

- [Strands Agents 1.0 공식 발표](https://aws.amazon.com/blogs/opensource/introducing-strands-agents-1-0-production-ready-multi-agent-orchestration-made-simple/)
- [Strands 멀티 에이전트 패턴 문서](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/)
- [Strands Graph 문서](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/graph/)
- [Strands Swarm 문서](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/swarm/)
- [Multi-Agent collaboration patterns with Strands](https://aws.amazon.com/blogs/machine-learning/multi-agent-collaboration-patterns-with-strands-agents-and-amazon-nova/)

---

## 12. Strands 내장 툴 (strands-agents-tools)

### 12.1 설치

```bash
pip install strands-agents-tools
```

`strands-agents`와 별개 패키지이므로 **별도 설치 필요**.

### 12.2 제공 툴 목록

#### 로컬 실행 (추가 비용 없음)

| 툴 | 용도 | 비고 |
|----|------|------|
| `calculator` | 수학 계산 | 순수 Python 연산 |
| `current_time` | 현재 시간 조회 | 시스템 시간 |
| `file_read` | 파일 읽기 | 로컬 파일 I/O |
| `file_write` | 파일 쓰기 | 로컬 파일 I/O |
| `editor` | 파일 편집 (문자열 교체 등) | 로컬 파일 I/O |
| `shell` | 쉘 명령어 실행 | 로컬 명령어 |
| `http_request` | HTTP API 호출 | 외부 API 비용은 별도 |

#### 외부 서비스 연동 (추가 비용 발생)

| 툴 | 백엔드 | 비용 |
|----|--------|------|
| `memory` | **Amazon Bedrock Knowledge Base** | OpenSearch + S3 + 임베딩 비용 |
| `mem0_memory` | **Mem0** 서비스 | Mem0 Cloud 또는 Self-hosted |
| `use_llm` | 추가 LLM 호출 | 토큰 비용 |

### 12.3 사용 예시

```python
from strands import Agent
from strands_tools import calculator, current_time, file_read, http_request

agent = Agent(tools=[calculator, current_time, file_read, http_request])

agent("What is 42 ^ 9")
agent("What time is it?")
agent("Show me the contents of config.json")
```

### 12.4 memory vs mem0_memory 비교

| 항목 | `memory` | `mem0_memory` |
|------|----------|---------------|
| **백엔드** | AWS Bedrock Knowledge Base | Mem0 서비스 |
| **저장소** | S3 + OpenSearch | Mem0 Cloud 또는 벡터DB |
| **비용** | 고정 비용 높음 (OpenSearch 최소 비용) | 무료 티어 10K memories |
| **적합 환경** | AWS 올인 | 멀티 클라우드, 로컬 개발 |

#### 비용 비교

| 규모 | 추천 |
|------|------|
| **소규모 (테스트)** | Mem0 무료 티어 또는 Self-hosted |
| **중규모 (프로덕션)** | 비슷함 (구성에 따라 다름) |
| **대규모 (AWS 환경)** | Bedrock KB (통합 관리, 볼륨 할인) |

### 12.5 Mem0 Self-hosted (Fargate 배포)

Mem0는 오픈소스로 직접 호스팅 가능. 단, Fargate는 stateless이므로 **외부 벡터 DB 필요**.

```python
from mem0 import Memory

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "your-qdrant-host.com",
            "port": 6333,
        }
    }
}

m = Memory.from_config(config)
```

#### 외부 벡터 DB 옵션

| 서비스 | 특징 |
|--------|------|
| **Amazon OpenSearch Serverless** | AWS 네이티브 |
| **Pinecone** | 무료 티어 있음 |
| **Qdrant Cloud** | 무료 티어 1GB |
| **PostgreSQL + pgvector** | RDS로 운영 가능 |

### 12.6 RAG에 추천하는 툴 조합

| 용도 | 툴 조합 |
|------|---------|
| **기본 RAG** | `memory` + `use_llm` |
| **웹 연동 RAG** | `memory` + `http_request` + `use_llm` |
| **문서 기반 RAG** | `memory` + `file_read` + 커스텀 `pdf_parser` |
| **하이브리드** | `memory` + `http_request` + `calculator` + `current_time` |

#### 커스텀 툴 예시

```python
from strands import tool

@tool
def web_search(query: str) -> str:
    """Google/Bing 검색 결과 반환"""
    # SerpAPI, Tavily 등 활용
    pass

@tool
def pdf_parser(file_path: str) -> str:
    """PDF에서 텍스트 추출"""
    pass

@tool
def db_query(sql: str) -> str:
    """데이터베이스 조회"""
    pass
```

### 12.7 참고 자료

- [Strands Tools Overview](https://strandsagents.com/latest/user-guide/concepts/tools/tools_overview/)
- [Mem0 공식 사이트](https://mem0.ai/)
- [Mem0 Pricing](https://mem0.ai/pricing)
