# STEP CB: 임베딩 클라이언트 구현

## 상태: 완료 ✅

## 완료된 작업
- [x] boto3 설치 (이미 설치됨)
- [x] AWS IAM 사용자 생성 및 권한 설정
- [x] Bedrock 모델 접근 활성화
- [x] EmbeddingClient 클래스 구현
- [x] 임베딩 테스트 성공

---

## 기술 스택

### AWS Bedrock
- 모델: `amazon.titan-embed-text-v2:0`
- 차원: 1024
- 리전: `us-east-1`

### IAM 권한
- 정책: `AmazonBedrockFullAccess`

---

## 구현 결과

### 환경 변수 (.env)

```bash
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-1
```

### EmbeddingClient 클래스

```python
# src/embedding_client.py
from embedding_client import EmbeddingClient

client = EmbeddingClient()
embedding = client.embed("텍스트")  # -> list[float] (1024차원)
```

### 테스트 결과

```
Model: amazon.titan-embed-text-v2:0
Region: us-east-1
Embedding dimension: 1024
First 5 values: [-0.049, 0.017, 0.023, -0.043, 0.062]
```

---

## 파일 구조

```
src/
  embedding_client.py    # 임베딩 클라이언트 클래스
```
