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

## 8. 마일스톤

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
