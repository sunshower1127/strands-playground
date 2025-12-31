# STEP CD: 쿼리 빌더 (QueryBuilder)

## 상태: 계획

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

## 할 일
- [ ] Protocol 정의
- [ ] KNNQueryBuilder 구현
- [ ] HybridQueryBuilder 구현
- [ ] 테스트 작성
