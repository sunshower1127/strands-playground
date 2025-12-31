# STEP CA: LLM 클라이언트 구현

## 상태: 완료 ✅

## 완료된 작업
- [x] anthropic[vertex] + google-cloud-aiplatform 설치
- [x] Vertex AI 인증 설정 (서비스 계정 JSON)
- [x] Claude 모델 연결 테스트
- [x] LLM 클라이언트 클래스 구현
- [x] 호출 테스트 성공

---

## 기술 스택

### anthropic[vertex]
- Anthropic 공식 SDK의 Vertex AI 확장
- LiteLLM 대신 공식 SDK 선택 (더 안정적)

### Vertex AI Claude
- Google Cloud를 통한 Claude 접근
- 모델: `claude-sonnet-4-5@20250929`
- 리전: `global`

---

## 구현 결과

### 환경 변수 (.env)

```bash
GCP_PROJECT_ID=smooth-zenith-468209-u1
GCP_REGION=global
VERTEX_CLAUDE_MODEL=claude-sonnet-4-5@20250929
```

### 인증 파일
- `credentials/gcp-service-account.json` (gitignore됨)

### LLM 클라이언트 클래스

```python
# src/llm_client.py
from anthropic import AnthropicVertex

class LLMClient:
    def call(self, prompt: str, system: str | None = None) -> LLMResponse:
        # Vertex AI Claude 호출
        ...
```

### 테스트 결과

```
Model: claude-sonnet-4-5@20250929
Project: smooth-zenith-468209-u1
Region: global

Content: 안녕하세요! 저는 Claude라는 AI 어시스턴트입니다...
Input tokens: 37
Output tokens: 82
```

---

## 파일 구조

```
src/
  llm_client.py          # LLM 클라이언트 클래스
scripts/
  test_llm.py            # 테스트 스크립트
credentials/
  gcp-service-account.json  # GCP 인증 (gitignore)
  README.md                 # 필요한 인증 파일 안내
```
