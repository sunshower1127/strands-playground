# STEP CD: 쿼리 빌더 (QueryBuilder)

## 상태: 완료

## 목표

전처리된 질문 + 임베딩 → OpenSearch 쿼리 생성

---

## 환경 정보

| 항목            | 값                                       |
| --------------- | ---------------------------------------- |
| OpenSearch 버전 | 7.10.2 (AWS OpenSearch Service)          |
| 인덱스          | `rag-index-fargate-live`                 |
| 벡터 필드       | `embedding` (1024 dim, lucene, hnsw, l2) |
| 텍스트 필드     | `text.ko` (nori analyzer), `text.en`     |
| 프로젝트 필터   | `project_id: 334`                        |

---

## 기존 Search Pipeline

```json
// hybrid-rrf (rank_constant=60)
{
  "phase_results_processors": [{
    "score-ranker-processor": {
      "combination": {
        "technique": "rrf",
        "rank_constant": 60
      }
    }
  }]
}

// hybrid-rrf-tuned (rank_constant=20)
{
  "phase_results_processors": [{
    "score-ranker-processor": {
      "combination": {
        "technique": "rrf",
        "rank_constant": 20
      }
    }
  }]
}
```

### rank_constant 값

- 높을수록 (60): 순위 차이 영향 감소, 부드러운 결합
- 낮을수록 (20): 상위 순위에 더 집중
- 권장값은 60

---

## 구현할 클래스

### Protocol 정의

```python
class QueryBuilder(Protocol):
    def build(
        self,
        query: str,
        embedding: list[float],
        project_id: int,
        k: int = 5,
    ) -> dict: ...
```

### 1. KNNQueryBuilder (베이스라인)

순수 벡터 검색:

```python
{
    "query": {
        "knn": {
            "embedding": {
                "vector": embedding,
                "k": k,
                "filter": {
                    "term": {"project_id": project_id}
                }
            }
        }
    }
}
```

**특징:**

- 가장 단순, 디버깅 용이
- 의미적 유사도만 사용
- 임베딩 품질에만 의존

**주의:** `bool.must`에 knn을 넣으면 점수가 제대로 안 나옴. `knn`을 최상위에 두고 `filter`를 내부에 넣어야 함.

### 2. HybridQueryBuilder

KNN + BM25 결합 (RRF 파이프라인 사용):

```python
{
    "query": {
        "hybrid": {
            "queries": [
                # BM25
                {
                    "bool": {
                        "must": [{"match": {"text.ko": query}}],
                        "filter": [{"term": {"project_id": project_id}}]
                    }
                },
                # KNN
                {
                    "knn": {
                        "embedding": {
                            "vector": embedding,
                            "k": k,
                            "filter": {"term": {"project_id": project_id}}
                        }
                    }
                }
            ]
        }
    }
}

# 검색 시 파이프라인 적용
response = client.search(
    index=index,
    body=query,
    params={"search_pipeline": "hybrid-rrf"}
)
```

**특징:**

- BM25 + KNN 결과를 RRF로 결합
- 튜닝 없이 안정적인 성능
- 키워드 + 의미 검색 모두 활용

---

## 참고: BM25 쿼리 (단독 사용 시)

```python
{
    "query": {
        "bool": {
            "must": [{"match": {"text.ko": query}}],
            "filter": [{"term": {"project_id": project_id}}]
        }
    }
}
```

별도 클래스로 구현하지 않음 - Hybrid에서 테스트 가능.

---

## RRF (Reciprocal Rank Fusion)

### 공식

```
score(doc) = Σ 1/(k + rank_i)
```

- `k`: rank_constant (기본값 60)
- `rank_i`: 각 쿼리에서의 문서 순위

### 특징

- **Plug & Play**: 가중치 튜닝 불필요
- **안정적**: 점수 범위, 이상치에 강건
- **유지보수 쉬움**: 데이터/쿼리 변화에도 재조정 불필요

---

## KNN k값 및 Hybrid size 권장값

### Reranker 사용 여부에 따른 권장값

| 파이프라인 | KNN `k` | Hybrid `size` | Reranker `top_n` | 최종 반환 |
|-----------|---------|---------------|------------------|----------|
| **KNN only** | 5~10 | - | - | 5~10 |
| **Hybrid (Rerank X)** | 50~100 | 5~10 | - | 5~10 |
| **Hybrid + Rerank** | 50~100 | 20~50 | 5~10 | 5~10 |

### 왜 이렇게 설정하나?

#### KNN `k` 값 (50~100 권장)

```
KNN k=10 + BM25 → RRF → 최대 20개 후보
KNN k=100 + BM25 → RRF → 최대 200개 후보

RRF는 순위 기반이므로 후보가 많을수록 좋은 문서를 찾을 확률 ↑
```

- **k가 너무 작으면**: BM25에서 높은 순위인데 KNN에서 못 찾은 문서가 누락
- **k가 너무 크면**: 성능 저하 (HNSW 그래프 탐색 비용 증가)
- **권장**: 50~100 (General RAG 기준)

#### Hybrid `size` 값

```
Rerank 없을 때: size = 최종 반환 개수 (5~10)
Rerank 있을 때: size = Reranker 입력 개수 (20~50)
```

- Reranker는 Cross-Encoder로 정밀하게 재정렬
- 더 많은 후보를 주면 좋은 문서를 재발견할 확률 ↑
- 너무 많으면 Reranker 비용 증가 (문서당 추론)

#### Reranker `top_n` 값

- 최종적으로 LLM 컨텍스트에 들어갈 문서 개수
- **5~10개 권장** (토큰 제한 고려)

### 예시 설정

#### 1. 단순 파이프라인 (Rerank X)

```python
# KNNQueryBuilder
k = 10  # 최종 반환

# HybridQueryBuilder
k = 50  # RRF 후보용
size = 5  # 최종 반환
```

#### 2. 고품질 파이프라인 (Rerank O)

```python
# HybridQueryBuilder
k = 100  # RRF 후보용
size = 30  # Reranker 입력

# Reranker
top_n = 5  # 최종 반환
```

### 성능 vs 품질 트레이드오프

| 설정 | 성능 | 품질 | 비용 | 권장 시나리오 |
|-----|------|------|------|-------------|
| k=20, size=5, no rerank | 빠름 | 보통 | 낮음 | 빠른 응답 우선 |
| k=50, size=10, no rerank | 보통 | 좋음 | 낮음 | 일반적인 RAG |
| k=100, size=30, rerank top_n=5 | 느림 | 높음 | 중간 | 품질 우선 |

---

## 한국어 Nori 설정 (참고)

### Nori가 필요한 이유

BM25는 토큰(단어) 매칭인데, 한국어는 띄어쓰기로 자르면 안 됨:

```
standard analyzer (띄어쓰기):
문서: "연차휴가는 15일입니다" → ["연차휴가는", "15일입니다"]
검색: "연차 휴가" → ["연차", "휴가"]
→ 매칭 실패 ❌

nori analyzer (형태소 분석):
문서: "연차휴가는 15일입니다" → ["연차", "휴가", "15", "일"]
검색: "연차 휴가" → ["연차", "휴가"]
→ 매칭 성공 ✅
```

### Nori 옵션

```json
{
  "tokenizer": {
    "nori_tokenizer": {
      "type": "nori_tokenizer",
      "decompound_mode": "discard" // 합성어 분리
    }
  },
  "filter": {
    "nori_part_of_speech": {
      "type": "nori_part_of_speech",
      "stoptags": ["E", "J", "MAJ", "XSA"] // 조사, 어미 등 제거
    }
  }
}
```

#### decompound_mode (합성어 처리)

| 모드      | "삼성전자" 결과              | 용도               |
| --------- | ---------------------------- | ------------------ |
| `none`    | ["삼성전자"]                 | 합성어 유지        |
| `discard` | ["삼성", "전자"]             | 분리만 (원본 버림) |
| `mixed`   | ["삼성전자", "삼성", "전자"] | 둘 다 유지         |

#### stoptags (품사 필터링)

| 태그  | 품사               | 예시                           | 제거 이유     |
| ----- | ------------------ | ------------------------------ | ------------- |
| `E`   | 어미               | "-다", "-는", "-고"            | 의미 없음     |
| `J`   | 조사               | "은", "는", "이", "가", "에서" | 의미 없음     |
| `MAJ` | 접속부사           | "그리고", "하지만"             | 검색에 불필요 |
| `XSA` | 형용사 파생 접미사 | "-스럽", "-롭"                 | 의미 희석     |

### 다국어 처리 전략

#### 옵션 비교

| 방식                        | 설명                                     | 복잡도 | 권장      |
| --------------------------- | ---------------------------------------- | ------ | --------- |
| **Nori + lowercase**        | 단일 analyzer로 한영 모두 처리           | 낮음   | ✅ 권장   |
| 멀티필드 (text.ko, text.en) | 같은 텍스트를 두 analyzer로 각각 인덱싱  | 중간   | ⚠️ 필요시 |
| 언어 감지 분기              | 인덱싱 시 언어 감지해서 다른 필드에 저장 | 높음   | ❌ 비효율 |

#### Nori의 영어 처리

```
입력: "Hello world 안녕하세요"
Nori: ["Hello", "world", "안녕", "하", "세요"]  // 띄어쓰기로 분리
```

**English Analyzer와 차이:**
| 항목 | Nori | English Analyzer |
|------|------|------------------|
| 대소문자 | "Hello" 그대로 | "hello"로 변환 |
| 어근 추출 | 안 함 | "running" → "run" |
| 불용어 | 한국어만 | "the", "a" 제거 |

**해결책:** `lowercase` 필터 추가

```json
"analyzer": {
  "nori_lowercase": {
    "tokenizer": "nori_tokenizer",
    "filter": ["lowercase", "nori_part_of_speech"]
  }
}
```

#### 권장 설정 (General RAG)

한국어 위주 + 영어 문서 섞여있는 경우:

```json
"chunk_text": {
  "type": "text",
  "analyzer": "nori_lowercase"
}
```

**이유:**

- Nori + lowercase로 한영 모두 처리 가능
- 영어 어근 추출 안 되지만, Hybrid 검색에서 KNN이 커버
- 멀티필드 대비 저장 공간 절약, 구현 단순

#### 주의사항

- **인덱싱/검색 analyzer 일치 필수**: 인덱스 필드에 analyzer 지정하면 양쪽 자동 적용
- **기존 인덱스 변경 불가**: analyzer 변경하려면 인덱스 재생성 필요 (reindex API로 데이터 복사)

---

## 구현 결정

| QueryBuilder       | 구현 | 이유                   |
| ------------------ | ---- | ---------------------- |
| KNNQueryBuilder    | O    | 베이스라인, 디버깅용   |
| BM25QueryBuilder   | X    | Hybrid에서 테스트 가능 |
| HybridQueryBuilder | O    | 최종 성능              |

---

## 테스트 결과 (조사 시 검증)

### KNN 검색

```
질문: "연차 휴가는 며칠인가?"

1. [0.5439] 휴가정책.txt - "# TechFlow Inc. 휴가 정책..."
2. [0.4661] 휴가정책.txt - "10월 1일 기준 잔여 연차가..."
3. [0.4387] 휴가정책.txt - "포상 휴가는 부여일로부터..."
```

### Hybrid 검색 (RRF)

```
1. [0.0328] 휴가정책.txt - "# TechFlow Inc. 휴가 정책..."
2. [0.0320] 휴가정책.txt - "10월 1일 기준 잔여 연차가..."
3. [0.0320] 휴가정책.txt - "포상 휴가는 부여일로부터..."
```

RRF 점수는 0.01~0.05 범위가 정상 (순위 기반 공식).

---

## 참고 자료

- [OpenSearch Hybrid Search Documentation](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/)
- [OpenSearch RRF Score Ranker](https://opensearch.org/blog/building-effective-hybrid-search-in-opensearch-techniques-and-best-practices/)
- [AWS OpenSearch Nori Plugin](https://aws.amazon.com/ko/blogs/tech/amazon-opensearch-service-korean-nori-plugin-for-analysis/)
- [AWS Hybrid Query 가이드](https://aws.amazon.com/ko/blogs/tech/amazon-opensearch-service-hybrid-query-korean/)

---

## 파일

- `src/rag/query_builder.py`
- `tests/test_query_builder.py`

---

## 튜닝 옵션 레퍼런스 (기존 프로젝트 분석)

### 1. 검색 필드 (multi_match) (굳이 안쓰는게 좋다는 결론)

```python
"fields": [
    "chunk_text^4.0",  # 기본 분석기 (가장 넓은 매칭)
    "text.ko^3.5",     # 한국어 nori 분석기
    "text.en^1.8"      # 영어 분석기
]
```

| 옵션             | 의미                           | 필요?               |
| ---------------- | ------------------------------ | ------------------- |
| `chunk_text^4.0` | 기본 분석기로 검색, 가중치 4배 | ✅ 필요             |
| `text.ko^3.5`    | nori 분석기로 한국어 검색      | ✅ 필요             |
| `text.en^1.8`    | 영어 분석기로 검색             | ⚠️ 영어 문서 있으면 |

---

### 2. multi_match 타입 옵션 (굳이 안쓰는게 좋다는 결론)

```python
"type": "cross_fields",
"operator": "OR",
"minimum_should_match": str(msm)  # 동적 계산
```

| 옵션                   | 의미                              | 필요?               |
| ---------------------- | --------------------------------- | ------------------- |
| `type: cross_fields`   | 여러 필드를 하나처럼 취급         | ⚠️ 검토 필요        |
| `type: best_fields`    | 가장 높은 점수 필드 사용 (기본값) | ✅ 단순             |
| `operator: OR`         | 단어 중 하나만 매칭해도 됨        | ✅ 기본값           |
| `minimum_should_match` | 최소 N개 단어는 매칭해야 함       | ⚠️ 짧은 쿼리 대응용 |

**MSM 동적 계산 (기존 프로젝트):**

```python
n = len(tokens)
if n <= 2: msm = 1
elif n <= 4: msm = 2
else: msm = max(1, int(n * 0.6))
```

---

### 3. function_score (최신성 보너스) (굳이 안쓰는게 좋다는 결론. 대신 답변에 포함시키는쪽으로)

```python
"function_score": {
    "query": { ... },
    "functions": [{
        "gauss": {
            "metadata.last_modified_at": {
                "origin": "now",
                "scale": "180d",   # 6개월 기준
                "decay": 0.8,     # 감쇠율
                "offset": "7d"    # 7일 이내는 최대 점수
            }
        },
        "weight": 0.25  # 전체 점수의 25%만 영향
    }],
    "score_mode": "multiply",
    "boost_mode": "multiply"
}
```

| 옵션           | 의미                    | 필요?           |
| -------------- | ----------------------- | --------------- |
| `gauss decay`  | 최근 문서에 점수 보너스 | ❌ 복잡, 나중에 |
| `scale: 180d`  | 6개월 기준으로 감쇠     | -               |
| `weight: 0.25` | 최신성이 25%만 영향     | -               |

---

### 4. bigram phrase 부스트 (굳이 안쓰는게 좋다는 결론)

```python
# 연속 단어 매칭 시 부스트
bigrams = ["연차 휴가", "휴가 정책"]
for phrase in bigrams:
    "match_phrase": {"text.ko": {"query": phrase, "slop": 1, "boost": 3.5}}
    "match_phrase": {"title.ko": {"query": phrase, "slop": 1, "boost": 2.8}}
```

| 옵션           | 의미                     | 필요?          |
| -------------- | ------------------------ | -------------- |
| `match_phrase` | 연속 단어 매칭 시 부스트 | ❌ 효과 불확실 |
| `slop: 1`      | 단어 사이 1개 갭 허용    | -              |
| `boost: 3.5`   | 매칭 시 3.5배 부스트     | -              |

---

### 5. 파일명 검색 (굳이 안쓰는게 좋다는 결론. 메타에 포함시키는게 그냥)

```python
# 파일명에 키워드 포함 시 부스트
"wildcard": {"file_name": {"value": "*휴가*", "boost": 1.2}}
"prefix": {"file_name": {"value": "휴가", "boost": 1.5}}
```

| 옵션       | 의미                   | 필요?      |
| ---------- | ---------------------- | ---------- |
| `wildcard` | 파일명에 키워드 포함   | ❌ 비용 큼 |
| `prefix`   | 파일명이 키워드로 시작 | ❌ 나중에  |

---

### 6. KNN 옵션

```python
"knn": {
    "embedding": {
        "vector": embedding,
        "k": 100,      # RRF용 후보 개수
        "boost": 0.7   # 텍스트 대비 벡터 가중치
    }
}
```

| 옵션         | 의미             | 필요?                                                  |
| ------------ | ---------------- | ------------------------------------------------------ |
| `k: 100`     | RRF용 후보 100개 | ✅ 권장                                                |
| `boost: 0.7` | 벡터 점수 0.7배  | ⚠️ 튜닝 대상(RRF에서는 필요없음. 결론적으로 필요없음.) |

---

### 7. 기타 옵션

```python
# RRF 후보 확대 (OpenSearch 2.19+) (버전때문에 불가? 있으면 좋다고는 함)
"pagination_depth": max(100, top_k * 4)

# 응답에서 벡터 제외 (성능)
"_source": {"excludes": ["embedding", "embedding_vector"]}
```

| 옵션                 | 의미           | 필요?        |
| -------------------- | -------------- | ------------ |
| `pagination_depth`   | RRF 후보 확대  | ⚠️ 버전 확인 |
| `excludes embedding` | 응답 크기 줄임 | ✅ 권장      |

---

### 구현 우선순위

**1단계 (필수):**

- `multi_match` with `chunk_text`, `text.ko`, `text.en`
- `knn` with filter
- `search_pipeline: hybrid-rrf`

**2단계 (튜닝):**

- 필드 `boost` 값 조정
- `knn boost` 조정
- `minimum_should_match` 추가

**3단계 (고급):**

- 최신성 보너스 (`function_score`)
- bigram phrase 부스트
- 파일명 검색

---

## 대규모 검색 대응

### 문서 규모별 특성

| 청크 수 | BM25 | KNN (HNSW) | Hybrid | 비고 |
|--------|------|------------|--------|------|
| ~10만 | ✅ 안정 | ✅ 빠름 (~10ms) | ✅ 권장 | 단일 노드 OK |
| ~30만 | ✅ 안정 | ✅ 빠름 (~20ms) | ✅ 권장 | 단일 노드 OK |
| 100만+ | ✅ 안정 | ⚠️ 튜닝 필요 | ✅ 권장 | 스케일업/샤딩 고려 |

### 규모 추정

```
파일 3,000개 가정:
- 평균 문서: 5~20 페이지
- 청크당 ~500토큰 (300~400자)
- 파일당 약 20~100 청크

→ 3,000파일 × 50청크(평균) = 150,000 청크
→ 범위: 60,000 ~ 300,000 청크
```

### ef_search 파라미터

HNSW 그래프에서 검색 시 탐색 범위 조절:

```
ef_search ↑ → 정확도 ↑, 속도 ↓
ef_search ↓ → 정확도 ↓, 속도 ↑
```

| ef_search | 정확도 | 속도 | 사용 시나리오 |
|-----------|--------|------|--------------|
| 50~100 | 보통 | 빠름 | 실시간 응답 우선 |
| 100~200 | 좋음 | 보통 | **일반 RAG 권장** |
| 300~500 | 높음 | 느림 | 정확도 중요 |

```json
// 인덱스 설정
{
  "settings": {
    "index.knn": true,
    "index.knn.algo_param.ef_search": 200
  }
}
```

### 샤딩 (Sharding)

데이터를 여러 조각으로 분할해서 분산 저장/처리:

```
100만 청크를 3개 샤드로:
┌─────────┐ ┌─────────┐ ┌─────────┐
│ 33만    │ │ 33만    │ │ 33만    │  ← 병렬 처리
│ 샤드 0  │ │ 샤드 1  │ │ 샤드 2  │
└─────────┘ └─────────┘ └─────────┘
```

#### 샤드 수 가이드

| 청크 수 | 권장 샤드 | 이유 |
|--------|----------|------|
| ~10만 | 1 | 오버헤드만 늘어남 |
| 10~50만 | 1-2 | 단일 샤드 성능 충분 |
| 50~100만 | 2-3 | 병렬 처리 이점 |
| 100만+ | 3-5 | 샤드당 30-50만 유지 |

#### 설정 방법

```json
// 인덱스 생성 시 (생성 후 변경 불가!)
PUT /rag-index
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1
  }
}
```

**주의**: `number_of_shards`는 인덱스 생성 시 고정. 변경하려면 reindex 필요.

### 100만 청크 이상 대응

1. **노드 스케일업**: 32GB+ RAM 노드
2. **샤딩 적용**: 3+ 샤드로 분산
3. **ef_search 튜닝**: 100~200 권장
4. **필터 활용**: `project_id` 필터로 실제 검색 범위 축소

### 모니터링 지표

| 지표 | 임계값 | 대응 |
|-----|-------|------|
| JVMMemoryPressure | > 80% | 스케일업 |
| SearchLatency p99 | > 500ms | 튜닝/스케일업 |
| ClusterStatus | red | 즉시 확인 |

---

## 파일 필터링 전략

### 현재 방식: terms 필터

```python
# 폴더 내 모든 파일 ID로 필터링
file_ids = get_all_file_ids_in_folder(folder_id)

query = {
    "filter": {
        "terms": {"file_id": file_ids}  # 배열로 전달
    }
}
```

### 파일 수별 성능

| 파일 수 | terms 필터 | 권장 |
|--------|-----------|------|
| ~100 | ✅ OK | 현재 방식 유지 |
| 100~500 | ✅ OK | 현재 방식 유지 |
| 500~1000 | ⚠️ 주의 | 모니터링 |
| 1000+ | ⚠️ 개선 고려 | folder_ids 방식 검토 |

### 잠재적 문제 (1000+ 파일)

```
1. 쿼리 크기: 4000개 ID × ~20자 = ~80KB
2. max_clause_count: 기본값 1024 → 에러 가능
3. 네트워크 오버헤드: 매 검색마다 ID 목록 전송
```

### 대안: folder_ids 메타데이터 (필요시)

```python
# 인덱싱 시 폴더 정보 저장
{
    "file_id": "file_123",
    "folder_ids": ["folder_a", "folder_b"],  # 상위 폴더들
    "chunk_text": "..."
}

# 검색 시 단일 값으로 필터
query = {
    "filter": {
        "term": {"folder_ids": "folder_a"}
    }
}
```

### folder_ids 도입 시점

- `too_many_clauses` 에러 발생
- 검색 레이턴시 p99 > 500ms
- file_ids 500개 이상 검색이 빈번

### 모니터링 추가 권장

```python
# 검색 시 file_ids 개수 로깅
logger.info(f"Search with {len(file_ids)} file_ids, folder={folder_id}")
```

---

## 할 일

- [x] Protocol 정의
- [x] KNNQueryBuilder 구현
- [x] HybridQueryBuilder 구현
- [x] 테스트 작성
