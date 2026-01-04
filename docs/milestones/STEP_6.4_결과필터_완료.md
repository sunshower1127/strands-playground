# STEP CE: 결과 필터 (ResultFilter)

## 상태: 완료

## 목표

검색 결과에서 품질 낮은 문서 제거

---

## 핵심 결론

### Hybrid + RRF 사용 시 규칙 기반 필터는 무의미

```
RRF 점수 예시:
1위: 0.0328
2위: 0.0320
3위: 0.0320
4위: 0.0312

→ 점수 차이가 너무 작아서 임계값/엘보우 탐지 의미 없음
→ RRF는 이미 "순위 기반 정규화"를 한 결과
```

| 필터 | RRF 이후 필요? | 이유 |
|-----|--------------|------|
| TopKFilter | ❌ | Hybrid `size`로 이미 처리됨 |
| ScoreThresholdFilter | ❌ | RRF 점수 범위가 좁아서 임계값 설정 어려움 |
| AdaptiveThresholdFilter | ❌ | RRF 점수 분포가 평탄해서 엘보우 탐지 무의미 |
| **Reranker** | ✅ | 유일하게 "질문+문서 함께 이해"하는 단계 |

### 권장 파이프라인

```
Hybrid(k=100, size=30) → Reranker(top_n=5) → LLM
```

---

## Reranker 선택 가이드

### 로컬 vs 클라우드 API

| 방식 | 장점 | 단점 | 권장 환경 |
|-----|------|------|----------|
| **로컬 (FlashRank)** | 무료, 빠름 | 영어 위주, 한국어 약함 | 로컬 테스트 |
| **로컬 (BGE-m3)** | 다국어 좋음, 무료 | 2.2GB, GPU 권장 | EC2 + GPU |
| **클라우드 API** | 관리 불필요, 다국어 | 유료 (저렴) | **서버리스 (권장)** |

### 서버리스 환경 = 클라우드 API 필수

```
Lambda/Fargate에서 로컬 모델 문제:
- FlashRank: 영어 위주, 한국어 약함
- BGE-m3: 2.2GB 모델, GPU 없음, 콜드스타트 시 타임아웃

→ 클라우드 Reranker API 사용이 정답
```

### 클라우드 Reranker 비교

| 서비스 | 모델 | 한국어 | 비용 | 권장도 |
|-------|------|-------|------|-------|
| **AWS Bedrock** | Cohere Rerank 3.5 | ✅ 100+ 언어 공식 | ~$0.001/1K queries | ✅ **권장** |
| Google Vertex | semantic-ranker | ❓ 문서 불명확 | 비슷 | ⚠️ 한국어 검증 필요 |
| Cohere 직접 | Rerank 3.5 | ✅ 100+ 언어 | ~$0.001/1K queries | ✅ |

### Bedrock Cohere Rerank 권장 이유

1. **한국어 100+ 언어 공식 지원** - 명시적으로 검증됨
2. **비용 사실상 무료** - LLM 비용의 0.01% 수준
3. **서버리스 친화적** - 모델 다운로드/관리 불필요
4. **AWS 통합** - 현재 인프라와 일관성

### 비용 분석

```
Bedrock Cohere Rerank:
$0.001 / 1K search units = 검색 1건당 약 $0.000001 (0.001원)

실사용 예시:
- 1,000 쿼리/일 → 월 $0.03 (약 40원)
- 10,000 쿼리/일 → 월 $0.30 (약 400원)
- 100,000 쿼리/일 → 월 $3 (약 4,000원)

vs LLM 비용:
- Claude Sonnet 1회: ~$0.01~0.05 (10~70원)
- Reranker 1회: ~$0.000001 (0.001원)
→ LLM 비용의 0.01%, 사실상 무료
```

### Reranker 스펙

| 항목 | Cohere Rerank 3.5 |
|-----|------------------|
| 최대 문서 수 | 1,000개/요청 |
| 문서당 최대 | 4,096 토큰 |
| 레이턴시 | ~100ms |
| 비용 구조 | 문서 수/크기 무관 (쿼리당 과금) |

---

## 배경 조사 결과 (2024-2025)

### OpenSearch 자체 기능

- `min_score`: 쿼리 레벨에서 최소 점수 필터링 가능
- `size` (Top K): 상위 K개 반환
- **주의**: Hybrid Query에서 `min_score`는 normalized 점수가 아닌 개별 서브쿼리에 적용됨

### 현대 RAG 파이프라인 권장 구조

```
[1단계: 검색] 빠르게 많이 (20~50개)
      ↓
[2단계: Reranking] 정밀하게 필터링 (3~5개)
```

### 왜 Reranking인가?

| 방식         | 판단 기준           | 정확도   |
| ------------ | ------------------- | -------- |
| BM25 점수    | 단어 겹침           | 낮음     |
| 벡터 유사도  | 방향 유사성         | 중간     |
| **Reranker** | 질문+문서 함께 이해 | **높음** |

> "Rerankers are much more accurate than embedding models" - Pinecone

---

## 구현할 클래스

### Protocol 정의

```python
class ResultFilter(Protocol):
    def filter(self, query: str, results: list[dict]) -> list[dict]: ...
```

### 1. NoopFilter (베이스라인)

- 필터링 안 함
- 검색 결과 그대로 반환
- 용도: 비교 기준

### 2. TopKFilter

- 상위 K개만 반환
- 단순하지만 효과적
- 권장값: k=5 (최종 출력), k=20~50 (Reranking 전)

### 3. ScoreThresholdFilter

- 고정 점수 임계값
- `min_score` 이상만 통과
- OpenSearch 쿼리에서도 처리 가능 (`"min_score": 0.5`)

```python
class ScoreThresholdFilter:
    def __init__(self, min_score: float = 0.5):
        self.min_score = min_score

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        return [r for r in results if r["_score"] >= self.min_score]
```

### 4. AdaptiveThresholdFilter (기존 로직 보존)

동적 임계값 계산:

- 점수 정규화 (max_score 기준)
- 엘보우(최대 갭) 탐지
- 분위수 기반 임계값
- 최소 보존 개수 보장 (3~8개)

```python
기존 파라미터:
- QUANTILE_PERCENTAGE = 0.15
- THRESHOLD_UPPER_BOUND = 0.9
- THRESHOLD_LOWER_BOUND = 0.1
- MIN_KEEP_COUNT = 3
- MAX_KEEP_COUNT = 8
```

**보존 이유**: 새 방식(Reranking) 대비 성능 비교 측정용

### 5. RerankerFilter (신규 - 권장)

Reranking 후 Top-K 반환

```python
class RerankerFilter:
    def __init__(self, model_name: str = "ms-marco-MiniLM-L-12-v2", top_k: int = 5):
        from rerankers import Reranker
        self.ranker = Reranker(model_name, model_type="flashrank")
        self.top_k = top_k

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        if not results:
            return results
        docs = [r["_source"]["content"] for r in results]
        ranked = self.ranker.rank(query=query, docs=docs)
        top_indices = [r.doc_id for r in ranked.results[:self.top_k]]
        return [results[i] for i in top_indices]
```

---

## 테스트할 라이브러리

### 1. FlashRank (우선 테스트)

```bash
pip install FlashRank
```

| 항목 | 내용                      |
| ---- | ------------------------- |
| 크기 | ~4MB (초경량)             |
| 속도 | CPU에서 빠름              |
| GPU  | 불필요                    |
| 비용 | 무료                      |
| 모델 | `ms-marco-MiniLM-L-12-v2` |

### 2. rerankers (Answer.AI)

```bash
pip install rerankers
# FlashRank 백엔드 사용시
pip install "rerankers[flashrank]"
```

| 항목   | 내용                                  |
| ------ | ------------------------------------- |
| 특징   | 통합 API (여러 백엔드 지원)           |
| 장점   | FlashRank, Cross-Encoder 등 쉽게 교체 |
| 의존성 | 기본 패키지는 의존성 없음             |

### 3. sentence-transformers Cross-Encoder (선택적)

```bash
pip install sentence-transformers
```

| 항목   | 내용                                  |
| ------ | ------------------------------------- |
| 정확도 | FlashRank보다 높음                    |
| 속도   | 느림                                  |
| GPU    | 권장                                  |
| 모델   | `cross-encoder/ms-marco-MiniLM-L6-v2` |

### (참고) 사용 안 함

- **Cohere Rerank API**: 최고 성능이지만 유료

---

## 평가 지표 (Evaluation Metrics)

### 순서 무관 지표 (Order-Unaware)

| 지표            | 설명                          | 계산                          |
| --------------- | ----------------------------- | ----------------------------- |
| **Precision@K** | 상위 K개 중 관련 문서 비율    | 관련문서수 / K                |
| **Recall@K**    | 전체 관련 문서 중 검색된 비율 | 검색된관련문서 / 전체관련문서 |
| **F1@K**        | Precision과 Recall의 조화평균 | 2 _ (P _ R) / (P + R)         |

```
예시: 관련 문서 10개 중 상위 5개에 3개 포함
- Precision@5 = 3/5 = 0.6
- Recall@5 = 3/10 = 0.3
```

### 순서 고려 지표 (Order-Aware) - 더 중요

| 지표       | 설명                               | 특징                    |
| ---------- | ---------------------------------- | ----------------------- |
| **MRR**    | 첫 번째 관련 문서 순위의 역수 평균 | 빠른 답변 찾기에 적합   |
| **NDCG@K** | 순위별 가중치 부여한 점수          | 검색 시스템 표준 지표   |
| **MAP@K**  | 각 관련 문서 위치의 Precision 평균 | 추천 시스템에 많이 사용 |

```
MRR 예시:
- Query1: 관련 문서가 1위 → 1/1 = 1.0
- Query2: 관련 문서가 3위 → 1/3 = 0.33
- MRR = (1.0 + 0.33) / 2 = 0.67
```

### 실용 지표

| 지표        | 설명                         |
| ----------- | ---------------------------- |
| **Latency** | 필터링 소요 시간 (ms)        |
| **Memory**  | 메모리 사용량                |
| **일관성**  | 같은 질문에 대한 결과 안정성 |

### 권장 목표치

- NDCG@10 >= 0.8
- MRR >= 0.7
- Precision@5 >= 0.6
- Latency < 100ms (FlashRank 기준)

---

## 테스트 계획

### Phase 1: 기본 기능 테스트

| 필터                      | 입력 10개 | 예상 출력       |
| ------------------------- | --------- | --------------- |
| NoopFilter                | 10개      | 10개            |
| TopKFilter(k=5)           | 10개      | 5개             |
| ScoreThresholdFilter(0.5) | 10개      | ?개 (점수 의존) |
| AdaptiveThresholdFilter   | 10개      | 3~8개           |
| RerankerFilter(top_k=5)   | 10개      | 5개 (재정렬됨)  |

### Phase 2: 라이브러리 비교 테스트

```
테스트 조건:
- 동일한 검색 결과 20개 입력
- 동일한 질문 세트 (최소 50개)
- 정답 레이블 필요 (어떤 문서가 관련있는지)
```

| 비교 항목    | FlashRank | Cross-Encoder | AdaptiveThreshold |
| ------------ | --------- | ------------- | ----------------- |
| NDCG@5       | ?         | ?             | ?                 |
| MRR          | ?         | ?             | ?                 |
| Latency (ms) | ?         | ?             | ?                 |
| Memory (MB)  | ?         | ?             | ?                 |

### Phase 3: 기존 vs 신규 방식 비교

```
AdaptiveThresholdFilter (기존) vs RerankerFilter (신규)

측정:
1. 동일 질문에 대해 최종 답변 품질 비교
2. 관련 문서 포함율 비교
3. 속도 비교
```

### 테스트 데이터셋 옵션

1. **직접 구축**: 프로젝트 문서로 질문-정답 쌍 50개 이상
2. **MS MARCO (참고용)**: 공개 벤치마크 데이터셋

---

## 구현 순서

```
1단계: 기존 방식 구현 (비교 기준)
├── NoopFilter
├── TopKFilter
├── ScoreThresholdFilter
└── AdaptiveThresholdFilter

2단계: 새 방식 구현 (Reranking)
├── FlashRank 기반 RerankerFilter
└── (선택) Cross-Encoder 기반 버전

3단계: 평가 도구 구현
├── 평가 지표 계산 함수 (NDCG, MRR, Precision, Recall)
└── 벤치마크 스크립트

4단계: 성능 비교 실험
├── 라이브러리별 비교
├── 기존 vs 신규 방식 비교
└── 최적 조합 결정
```

---

## 파일 구조

```
src/rag/
├── result_filter.py          # 필터 구현
└── filter_evaluation.py      # 평가 도구

tests/
├── test_result_filter.py     # 단위 테스트
└── benchmark_filters.py      # 벤치마크 스크립트
```

## 의존성 추가

```toml
# pyproject.toml
[project.optional-dependencies]
rerank = [
    "rerankers[flashrank]",
    # "sentence-transformers",  # Cross-Encoder 사용시
]
```

---

## 할 일

- [ ] Protocol 정의 (query 파라미터 추가)
- [ ] NoopFilter 구현
- [ ] TopKFilter 구현
- [ ] ScoreThresholdFilter 구현
- [ ] AdaptiveThresholdFilter 구현 (기존 로직 포팅)
- [ ] RerankerFilter 구현 (FlashRank)
- [ ] 평가 지표 계산 함수 구현 (NDCG, MRR, Precision, Recall)
- [ ] 테스트 데이터셋 구축 (질문-정답 쌍)
- [ ] 라이브러리 벤치마크 실행
- [ ] 기존 vs 신규 방식 성능 비교 리포트 작성

---

## 참고 자료

- [OpenSearch Vector Radial Search](https://opensearch.org/blog/vector-radial-search/)
- [Pinecone - Rerankers](https://www.pinecone.io/learn/series/rag/rerankers/)
- [FlashRank GitHub](https://github.com/PrithivirajDamodaran/FlashRank)
- [rerankers GitHub](https://github.com/AnswerDotAI/rerankers)
- [Weaviate - Retrieval Evaluation Metrics](https://weaviate.io/blog/retrieval-evaluation-metrics)
- [RAG Evaluation Metrics Guide](https://medium.com/@autorag/tips-to-understand-rag-retrieval-metrics-71e9a2bd4b96)
- [Relevance Filtering Research (2024)](https://arxiv.org/html/2408.04887v1)

---

## Bedrock Cohere Rerank 구현 예시

```python
import json
import boto3


class BedrockReranker:
    """AWS Bedrock Cohere Rerank 클라이언트"""

    def __init__(
        self,
        model_id: str = "cohere.rerank-v3-5:0",
        region: str = "us-east-1",
        top_n: int = 5,
    ):
        self.model_id = model_id
        self.top_n = top_n
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def rerank(self, query: str, documents: list[str]) -> list[dict]:
        """문서 재정렬

        Args:
            query: 사용자 질문
            documents: 재정렬할 문서 텍스트 리스트

        Returns:
            재정렬된 결과 [{index, relevance_score}, ...]
        """
        if not documents:
            return []

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "query": query,
                "documents": documents,
                "top_n": self.top_n,
            }),
        )

        result = json.loads(response["body"].read())
        return result["results"]  # [{index, relevance_score}, ...]


class RerankerFilter:
    """Reranker 기반 결과 필터"""

    def __init__(self, top_n: int = 5):
        self.reranker = BedrockReranker(top_n=top_n)
        self.top_n = top_n

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        if not results:
            return results

        # 문서 텍스트 추출
        docs = [r["_source"].get("chunk_text", "") for r in results]

        # Rerank
        ranked = self.reranker.rerank(query, docs)

        # 원본 결과에서 상위 N개 추출 (순서 유지)
        reranked_results = []
        for item in ranked:
            idx = item["index"]
            result = results[idx].copy()
            result["_rerank_score"] = item["relevance_score"]
            reranked_results.append(result)

        return reranked_results
```

---

## 로컬 Reranker 옵션 (참고용)

> 서버리스 환경에서는 권장하지 않음. 로컬 테스트/EC2+GPU 환경용.

### 2025 Reranker 비교

| 모델                         | 정확도    | 속도      | 비용 | 다국어  | 특징             |
| ---------------------------- | --------- | --------- | ---- | ------- | ---------------- |
| **FlashRank**                | Good      | Very Fast | Free | ⚠️ 영어 위주 | ONNX, CPU 최적화 |
| **BGE-reranker-v2-m3**       | High      | Moderate  | Free | ✅      | 2.2GB, GPU 권장  |
| **Cohere Rerank 3.5**        | High      | Fast      | API  | ✅ 100+ | **프로덕션 권장** |

### FlashRank (로컬 테스트용)

```python
from flashrank import Ranker

ranker = Ranker()  # 첫 실행 시 ~4MB 모델 다운로드
results = ranker.rerank(query="연차 휴가", documents=["문서1...", "문서2..."])
```

- 장점: 빠름, CPU OK, 무료
- 단점: **한국어 약함** (MS MARCO = 영어 데이터셋)

### BGE-reranker-v2-m3 (EC2+GPU용)

```python
from sentence_transformers import CrossEncoder

model = CrossEncoder("BAAI/bge-reranker-v2-m3")
scores = model.predict([("질문", "문서1"), ("질문", "문서2")])
```

- 장점: 다국어 좋음, 무료
- 단점: 2.2GB, GPU 권장, 서버리스 부적합

### 참고 자료

- [ZeroEntropy - Best Reranking Model 2025](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025)
- [Agentset Reranker Leaderboard](https://agentset.ai/rerankers)
- [Cohere Rerank on Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-cohere-rerank.html)
