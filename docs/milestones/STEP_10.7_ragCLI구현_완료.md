# STEP 10.7: RAG CLI 구현 (완료)

## 목표
Strands Agent 기반 대화형 REPL CLI 도구 구현
- 대화형 REPL 모드
- 파일 기반 세션 (시작 시 생성, 종료 시 삭제)
- Interrupt 기능 (ask_user 도구)

---

## 1. 파일 구조

### 1.1 생성할 파일
```
src/cli/
├── __init__.py           # CLI 모듈 초기화
├── main.py               # REPL 메인 루프 (진입점)
├── session.py            # 세션 관리 (생성/삭제)
├── commands.py           # 특수 명령어 (/help, /exit, /mode 등)
└── display.py            # 출력 포맷팅 (색상, 프롬프트)

src/agent/
├── unified_agent.py      # 세션 기반 통합 Agent
└── tools/
    └── ask_user.py       # 사용자 질문 도구 (interrupt)
```

### 1.2 수정할 파일
| 파일 | 변경 |
|------|------|
| `pyproject.toml` | `rag-chat` entry point 추가 |
| `src/agent/__init__.py` | UnifiedAgent export 추가 |

---

## 2. 구현 순서

### Phase 1: CLI 기본 구조
1. `src/cli/__init__.py` - 모듈 초기화
2. `src/cli/display.py` - 색상, 프롬프트, 출력 포맷팅
3. `src/cli/session.py` - CLISessionManager (FileSessionManager 래핑)
4. `pyproject.toml` - entry point: `rag-chat = "src.cli.main:main"`

### Phase 2: 통합 Agent
5. `src/agent/unified_agent.py` - UnifiedAgent 클래스
   - 세션/컨텍스트 관리
   - 모드 전환 (normal/agent)
   - query() / resume() 메서드
6. `src/agent/__init__.py` - export 추가

### Phase 3: Interrupt 시스템
7. `src/agent/tools/ask_user.py` - ask_user 도구
   - tool_context.interrupt() 호출
8. `src/cli/main.py` - interrupt 처리 루프

### Phase 4: 명령어 및 마무리
9. `src/cli/commands.py` - CommandHandler
10. `src/cli/main.py` - REPL 클래스 완성

---

## 3. 핵심 컴포넌트

### 3.1 CLISessionManager (session.py)
```python
class CLISessionManager:
    def create_session(self) -> FileSessionManager:
        self.session_id = f"cli-{uuid.uuid4().hex[:8]}"
        return FileSessionManager(session_id=self.session_id, storage_dir="./sessions")

    def cleanup(self) -> None:
        # 세션 파일 삭제 (persist=False일 때)
```

### 3.2 UnifiedAgent (unified_agent.py)
```python
class UnifiedAgent:
    def __init__(self, session_manager, project_id=334):
        self.conversation_manager = SlidingWindowConversationManager(window_size=20)
        # 도구: search_documents, tavily_search, ask_user

    def query(self, question: str) -> AgentResult
    def resume(self, responses: list[dict]) -> AgentResult
    def set_mode(self, mode: Literal["normal", "agent"])
```

### 3.3 ask_user 도구 (ask_user.py)
```python
@tool(context=True)
def ask_user(tool_context: ToolContext, question: str) -> str:
    return tool_context.interrupt("ask_user", reason={"question": question})
```

### 3.4 REPL 루프 (main.py)
```python
while True:
    user_input = input("You > ")
    if user_input.startswith("/"):
        handle_command(user_input)
    else:
        result = agent.query(user_input)
        while result.stop_reason == "interrupt":
            result = handle_interrupts(result)  # 사용자 입력 받고 resume
        display_answer(result)
```

---

## 4. 명령어

| 명령어 | 기능 |
|--------|------|
| `/help` | 도움말 |
| `/exit`, `/quit`, `/q` | 종료 |
| `/clear` | 화면 지우기 |
| `/mode [normal\|agent]` | 모드 전환/확인 |
| `/status` | 세션 정보 |

---

## 5. 실행 방법

```bash
uv run rag-chat
uv run rag-chat --project-id 334 --mode agent
uv run rag-chat --persist  # 종료 시 세션 유지
```

---

## 6. 마일스톤

- [x] Phase 1: CLI 기본 구조 (display, session, pyproject.toml)
- [x] Phase 2: UnifiedAgent 구현
- [x] Phase 3: ask_user 도구 + Interrupt 처리
- [x] Phase 4: 명령어 + REPL 완성
- [x] 테스트 및 검증

---

## 7. 구현 결과

### 생성된 파일
| 파일 | 설명 |
|------|------|
| `src/cli/__init__.py` | CLI 모듈 초기화 |
| `src/cli/display.py` | 터미널 출력 포맷팅 (색상, 프롬프트) |
| `src/cli/session.py` | CLISessionManager (세션 생성/삭제) |
| `src/cli/commands.py` | 명령어 핸들러 (/help, /exit, /mode 등) |
| `src/cli/main.py` | REPL 메인 루프 |
| `src/agent/unified_agent.py` | 세션 기반 통합 Agent |
| `src/agent/tools/ask_user.py` | 사용자 질문 도구 (interrupt) |

### 수정된 파일
| 파일 | 변경 |
|------|------|
| `pyproject.toml` | build-system, hatch config, rag-chat entry point 추가 |
| `src/agent/__init__.py` | UnifiedAgent export 추가 |
| `README.md` | CLI 사용법 문서화 |

---

## 8. 테스트 결과

### 동작 확인된 기능
- **세션 유지**: 대화 컨텍스트가 유지됨 (멀티턴 대화 가능)
- **도구 선택**: 내부 검색(`search_documents`)과 웹 검색(`tavily_search`) 조합
- **명확화 질문**: 불명확한 질문에 자연스럽게 추가 질문
- **종합 분석**: 내부 문서 + 외부 트렌드 비교 분석

### 수정 이력
- 답변 중복 출력 버그 수정 (스트리밍 + display.answer 중복 → 스트리밍만 유지)
