# STEP 1: 환경 설정 및 OpenSearch 연결

## 완료 항목

- [x] Python 프로젝트 초기화 (uv, Python 3.11)
- [x] 의존성 설치
- [x] OpenSearch 클라이언트 구현
- [x] SSH 터널 설정 (VPC 접근)
- [x] OpenSearch 연결 테스트 성공

---

## 1. 프로젝트 초기화

```bash
uv init --python 3.11
uv add opensearch-py litellm python-dotenv pydantic pandas boto3
uv add --dev ruff
```

## 2. 환경 변수

`.env.example` → `.env` 복사 후 설정:

```env
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=your-password
OPENSEARCH_INDEX=your-index
```

## 3. SSH 터널 (VPC OpenSearch 접근)

OpenSearch가 VPC 내부에 있어 직접 접근 불가. Bastion 서버를 통한 SSH 터널링 사용.

```bash
make tunnel
```

- 키 파일: `temp-bastion-key.cer` (프로젝트 루트, gitignore 처리됨)
- 로컬 포트 9443 → 원격 OpenSearch 443

## 4. 명령어 (Makefile)

| 명령어                 | 설명                     |
| ---------------------- | ------------------------ |
| `make tunnel`          | SSH 터널 열기            |
| `make test-opensearch` | 연결 테스트              |
| `make dashboard`       | OpenSearch 대시보드 열기 |
| `make format`          | 코드 포맷팅              |
| `make lint`            | 린트 검사                |

## 5. 테스트 결과

```bash
# 터미널 1
make tunnel

# 터미널 2
make test-opensearch
```

성공 출력:

```
Connecting to: localhost
✓ Connected! Cluster: xxx, Version: 2.x.x
✓ Indices count: N
```

---

## 다음 단계

- [ ] LLM 호출 테스트 (Vertex AI Claude)
- [ ] 기본 RAG 파이프라인 구현
