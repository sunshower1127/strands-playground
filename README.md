# Strands Playground

Strands Agent 기반 RAG (Retrieval-Augmented Generation) 시스템

## 주요 기능

- **문서 검색**: OpenSearch 기반 하이브리드 검색 (BM25 + KNN)
- **웹 검색**: Tavily API를 통한 실시간 웹 정보 검색
- **AI 답변**: Claude Sonnet 4.5 기반 질문 답변
- **대화형 CLI**: 세션 기반 REPL 인터페이스

## CLI 보충설명

- data/test_docs 폴더에 있는 문서를 Wissly를 통해서 OpenSearch에 업로드했습니다.
- 해당 폴더의 프로젝트 아이디는 334번 입니다.
- CLI를 통해 기억되고 있는 세션은 sessions 폴더에 저장되고 있습니다.

---

## 빠른 시작 (uv 사용) (uv는 npm같은 패키지 매니저입니다)

> uv가 설치되어 있다면 이 방법을 권장합니다.(uv가 없다면 아래 pip 사용으로)

```bash
# 1. 설치
uv sync

# 2. 환경 변수 설정 & credentials/ 폴더에 인증서 파일 배치
cp .env.example .env
# .env 파일에 API 키 입력

# 3. 터널 연결 (터미널 1 - 계속 열어두기)
make tunnel

# 4. CLI 실행 (터미널 2) 334번 프로젝트(data/test_docs를 wissly로 업로드시켰음)
uv run rag-chat

# 5. 추천 질문

1. 그것좀 알고 싶은데
2. 그 2024 IT 트렌드 중 우리 로드맵에 반영된 것이 뭐가 있을까?
3. (만약 우리 로드맵에 대한 설명을 보충해달라고 하면) 제품팀!

# 6. 다른 프로젝트 id를 사용하고 싶다면
uv run rag-chat --project-id 프로젝트아이디

```

---

## 빠른 시작 (pip 사용) (맥 전용)

> uv가 없다면 pip으로도 사용 가능합니다.

```bash
# 1. 설치
make install
# 또는
pip install -r requirements.txt

# 2. 환경 변수 설정 & credentials/ 폴더에 인증서 파일 배치
cp .env.example .env
# .env 파일에 API 키 입력

# 2.5. 권한 변경(필수)
chmod 600 ./credentials/temp-bastion-key.cer

# 3. 터널 연결 (터미널 1 - 계속 열어두기)
make tunnel

# 4. CLI 실행 (터미널 2) 334번 프로젝트(data/test_docs를 wissly로 업로드시켰음)
make chat

# 5. 추천 질문

1. 그것좀 알고 싶은데
2. 그 2024 IT 트렌드 중 우리 로드맵에 반영된 것이 뭐가 있을까?
3. (만약 우리 로드맵에 대한 설명을 보충해달라고 하면) 제품팀!

# 6. 다른 프로젝트 id를 사용하고 싶다면
make chat ARGS="--project-id 프로젝트아이디"
```

---

## CLI 명령어

| 명령어                  | 설명           |
| ----------------------- | -------------- |
| `/help`                 | 도움말 표시    |
| `/exit`, `/quit`, `/q`  | CLI 종료       |
| `/clear`                | 화면 지우기    |
| `/mode [normal\|agent]` | 모드 전환/확인 |
| `/status`               | 세션 정보 표시 |

## CLI 모드

| 모드     | 모델          | 도구                     | 용도                      |
| -------- | ------------- | ------------------------ | ------------------------- |
| `normal` | Claude Haiku  | 없음                     | 일반 대화                 |
| `agent`  | Claude Sonnet | search, tavily, ask_user | 문서/웹 검색, 복잡한 질문 |

## CLI 옵션

```bash
# 기본 실행
make chat

# 옵션과 함께 실행
make chat ARGS="--project-id 334"
make chat ARGS="--mode normal"
make chat ARGS="--persist"  # 종료 시 세션 유지 (세션은 sessions 폴더에서 보관중)
```

---

## Make 명령어

| 명령어           | 설명                                    |
| ---------------- | --------------------------------------- |
| `make install`   | pip로 의존성 설치                       |
| `make tunnel`    | OpenSearch 터널 연결 (CLI 실행 전 필수) |
| `make chat`      | RAG Chat CLI 실행 (pip)                 |
| `make dashboard` | OpenSearch 대시보드 열기                |
| `make format`    | 코드 포맷팅                             |
| `make lint`      | 코드 린트                               |
| `make test`      | 테스트 실행                             |

---

## 환경 변수

```bash
# OpenSearch
OPENSEARCH_USERNAME=your-username
OPENSEARCH_PASSWORD=your-password
OPENSEARCH_INDEX=your-index

# GCP Vertex AI (Claude)
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-east5

# AWS Bedrock (Embedding)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1

# Tavily (Web Search)
TAVILY_API_KEY=tvly-your-api-key
```

---

## 프로젝트 구조

```
src/
├── agent/                  # Strands Agent
│   ├── rag_agent.py       # 단일 쿼리 Agent
│   ├── unified_agent.py   # 세션 기반 통합 Agent
│   └── tools/             # Agent 도구
│       ├── search.py      # 문서 검색
│       └── ask_user.py    # 사용자 질문 (interrupt)
├── cli/                    # CLI 모듈
│   ├── main.py            # REPL 메인 루프
│   ├── session.py         # 세션 관리
│   ├── commands.py        # 명령어 처리
│   └── display.py         # 출력 포맷팅
├── rag/                    # Basic RAG 파이프라인
└── opensearch_client.py    # OpenSearch 클라이언트
```

---

## 요구사항

- Python 3.11+
- OpenSearch 터널 접근 (`credentials/temp-bastion-key.cer` 필요)
- GCP 서비스 계정 (`credentials/gcp-service-account.json` 필요)
