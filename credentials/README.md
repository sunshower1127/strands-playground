# Credentials

이 폴더에 필요한 인증 파일들:

| 파일명 | 용도 | 발급처 |
|--------|------|--------|
| `gcp-service-account.json` | Vertex AI Claude API 인증 | GCP Console > IAM > Service Accounts |
| `temp-bastion-key.cer` | OpenSearch SSH 터널용 | AWS Bastion 서버 키 |

## 환경변수 설정

`.env` 파일에 다음 설정 필요:

```bash
GOOGLE_APPLICATION_CREDENTIALS=credentials/gcp-service-account.json
```
