# STEP CD: 쿼리 빌더 (QueryBuilder)

## 상태: 완료

## 목표
전처리된 질문 + 임베딩 → OpenSearch 쿼리 생성

---

## 환경 정보

| 항목 | 값 |
|------|-----|
| OpenSearch 버전 | 7.10.2 (AWS OpenSearch Service) |
| 인덱스 | `rag-index-fargate-live` |
| 벡터 필드 | `embedding` (1024 dim, lucene, hnsw, l2) |
| 텍스트 필드 | `text.ko` (nori analyzer), `text.en` |
| 프로젝트 필터 | `project_id: 334` |

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

## 한국어 Nori 설정 (참고)

### 인덱스에 이미 설정됨
- `text.ko`: nori analyzer (ko_index, ko_search)
- `text.en`: english analyzer

### Nori 옵션 참고
```json
{
  "tokenizer": {
    "nori_tokenizer": {
      "type": "nori_tokenizer",
      "decompound_mode": "discard"  // 합성어 분리
    }
  },
  "filter": {
    "nori_part_of_speech": {
      "type": "nori_part_of_speech",
      "stoptags": ["E", "J", "MAJ", "XSA"]  // 조사, 어미 등 제거
    }
  }
}
```

---

## 구현 결정

| QueryBuilder | 구현 | 이유 |
|--------------|------|------|
| KNNQueryBuilder | O | 베이스라인, 디버깅용 |
| BM25QueryBuilder | X | Hybrid에서 테스트 가능 |
| HybridQueryBuilder | O | 최종 성능 |

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

### 1. 검색 필드 (multi_match)

```python
"fields": [
    "chunk_text^4.0",  # 기본 분석기 (가장 넓은 매칭)
    "text.ko^3.5",     # 한국어 nori 분석기
    "text.en^1.8"      # 영어 분석기
]
```

| 옵션 | 의미 | 필요? |
|------|------|-------|
| `chunk_text^4.0` | 기본 분석기로 검색, 가중치 4배 | ✅ 필요 |
| `text.ko^3.5` | nori 분석기로 한국어 검색 | ✅ 필요 |
| `text.en^1.8` | 영어 분석기로 검색 | ⚠️ 영어 문서 있으면 |

---

### 2. multi_match 타입 옵션

```python
"type": "cross_fields",
"operator": "OR",
"minimum_should_match": str(msm)  # 동적 계산
```

| 옵션 | 의미 | 필요? |
|------|------|-------|
| `type: cross_fields` | 여러 필드를 하나처럼 취급 | ⚠️ 검토 필요 |
| `type: best_fields` | 가장 높은 점수 필드 사용 (기본값) | ✅ 단순 |
| `operator: OR` | 단어 중 하나만 매칭해도 됨 | ✅ 기본값 |
| `minimum_should_match` | 최소 N개 단어는 매칭해야 함 | ⚠️ 짧은 쿼리 대응용 |

**MSM 동적 계산 (기존 프로젝트):**
```python
n = len(tokens)
if n <= 2: msm = 1
elif n <= 4: msm = 2
else: msm = max(1, int(n * 0.6))
```

---

### 3. function_score (최신성 보너스)

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

| 옵션 | 의미 | 필요? |
|------|------|-------|
| `gauss decay` | 최근 문서에 점수 보너스 | ❌ 복잡, 나중에 |
| `scale: 180d` | 6개월 기준으로 감쇠 | - |
| `weight: 0.25` | 최신성이 25%만 영향 | - |

---

### 4. bigram phrase 부스트

```python
# 연속 단어 매칭 시 부스트
bigrams = ["연차 휴가", "휴가 정책"]
for phrase in bigrams:
    "match_phrase": {"text.ko": {"query": phrase, "slop": 1, "boost": 3.5}}
    "match_phrase": {"title.ko": {"query": phrase, "slop": 1, "boost": 2.8}}
```

| 옵션 | 의미 | 필요? |
|------|------|-------|
| `match_phrase` | 연속 단어 매칭 시 부스트 | ❌ 효과 불확실 |
| `slop: 1` | 단어 사이 1개 갭 허용 | - |
| `boost: 3.5` | 매칭 시 3.5배 부스트 | - |

---

### 5. 파일명 검색

```python
# 파일명에 키워드 포함 시 부스트
"wildcard": {"file_name": {"value": "*휴가*", "boost": 1.2}}
"prefix": {"file_name": {"value": "휴가", "boost": 1.5}}
```

| 옵션 | 의미 | 필요? |
|------|------|-------|
| `wildcard` | 파일명에 키워드 포함 | ❌ 비용 큼 |
| `prefix` | 파일명이 키워드로 시작 | ❌ 나중에 |

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

| 옵션 | 의미 | 필요? |
|------|------|-------|
| `k: 100` | RRF용 후보 100개 | ✅ 권장 |
| `boost: 0.7` | 벡터 점수 0.7배 | ⚠️ 튜닝 대상 |

---

### 7. 기타 옵션

```python
# RRF 후보 확대 (OpenSearch 2.19+)
"pagination_depth": max(100, top_k * 4)

# 응답에서 벡터 제외 (성능)
"_source": {"excludes": ["embedding", "embedding_vector"]}
```

| 옵션 | 의미 | 필요? |
|------|------|-------|
| `pagination_depth` | RRF 후보 확대 | ⚠️ 버전 확인 |
| `excludes embedding` | 응답 크기 줄임 | ✅ 권장 |

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

## 할 일
- [x] Protocol 정의
- [x] KNNQueryBuilder 구현
- [x] HybridQueryBuilder 구현
- [x] 테스트 작성
