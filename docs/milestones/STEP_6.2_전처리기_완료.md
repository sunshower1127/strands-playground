# STEP CC: 쿼리 전처리기 (Preprocessor)

## 상태: 완료

- [x] `NoopPreprocessor` 구현
- [x] `MinimalPreprocessor` 구현
- [x] `KoreanPreprocessor` 구현

## 목표

사용자 질문을 검색에 최적화된 형태로 변환

---

## 조사 결과 요약

### 1. OpenSearch Nori가 이미 처리하는 것들

| 처리 항목                | Nori 자동 처리 | 비고                                           |
| ------------------------ | -------------- | ---------------------------------------------- |
| 조사 (은/는/이/가/을/를) | ✅             | `nori_part_of_speech` 기본 stoptags에 "J" 포함 |
| 어미 (E)                 | ✅             | 기본 stoptags에 "E" 포함                       |
| 형태소 분석              | ✅             | 자동 토크나이징                                |
| 복합어 분리              | ✅             | `decompound_mode: discard`                     |

**결론:** BM25 검색 시 Nori가 조사/어미를 자동 제거함. 별도 전처리 불필요.

### 2. 임베딩 모델에서 전처리 효과

| 의견                                       | 출처                                                                                                    |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| "불용어 제거가 결과에 유리하지 않았다"     | [OpenAI 커뮤니티](https://community.openai.com/t/text-pre-processing-for-text-embedding-ada-002/315997) |
| "워드 임베딩 훈련 시 불용어 제거 불필요"   | [Microsoft NLP Issues](https://github.com/microsoft/nlp-recipes/issues/395)                             |
| "BERT 기반 모델은 문맥 이해에 불용어 필요" | 일반적 견해                                                                                             |

**결론:** 최신 임베딩 모델(Titan 등)은 문맥을 이해하므로 전처리 효과 미미하거나 오히려 해로울 수 있음.

### 3. 기존 프로젝트 전처리 로직 분석

```python
def _remove_korean_particles(query: str) -> str:
    # 1) 유니코드 정규화 (NFKC)
    # 2) 양끝 문장부호/공백 정리
    # 3) 문장 종결어미 제거 (알려줘, 해주세요 등)
    # 4) 숫자 단위 정규화 (2024년 → 2024)
```

**분석:**

- 유니코드 정규화: 의미 있음 (특히 한글 자모 정규화)
- 문장부호 정리: 의미 있음
- 종결어미 제거: Nori가 처리하므로 BM25에서 중복, 임베딩에서는 효과 불명확
- 숫자 단위: "2024년" vs "2024" - 테스트 필요

### 4. 외부 라이브러리 비교

| 라이브러리            | 장점                                | 단점                  | 추천 |
| --------------------- | ----------------------------------- | --------------------- | ---- |
| **kiwipiepy**         | 빠름, 순수 Python, 불용어 필터 내장 | 의존성 추가           | △    |
| **KoNLPy**            | 다양한 분석기 (Mecab, Komoran)      | JVM 의존성, 설치 복잡 | X    |
| **직접 구현 (regex)** | 의존성 없음, 단순                   | 기능 제한             | ○    |
| **전처리 안 함**      | 가장 단순                           | -                     | ◎    |

---

## 결론: 전처리기 필요 없음 (또는 최소화)

### 이유

1. **BM25 검색**: Nori가 조사/어미 자동 처리
2. **벡터 검색**: 임베딩 모델이 문맥 이해, 전처리 효과 미미
3. **하이브리드 검색 (RRF)**: 둘 다 작동하면 됨

### 권장 구현

```python
class Preprocessor(Protocol):
    def process(self, query: str) -> str: ...

class NoopPreprocessor:
    """아무것도 안 함 (권장)"""
    def process(self, query: str) -> str:
        return query

class MinimalPreprocessor:
    """최소 정규화만 (선택적)"""
    def process(self, query: str) -> str:
        import unicodedata
        # 유니코드 정규화만 (NFKC)
        return unicodedata.normalize('NFKC', query).strip()
```

### 기존 KoreanPreprocessor는?

기존 프로젝트의 `_remove_korean_particles` 로직:

- **유니코드 정규화**: 유지 가치 있음
- **종결어미 제거**: 효과 불명확, 테스트 후 결정
- **숫자 단위 정규화**: 효과 불명확, 테스트 후 결정

→ 일단 **NoopPreprocessor**로 시작, 검색 품질 문제 발생 시 추가

---

## 테스트 계획

파이프라인 완성 후 비교 테스트:

| 전처리기            | 테스트         |
| ------------------- | -------------- |
| NoopPreprocessor    | 기준선         |
| MinimalPreprocessor | 유니코드만     |
| KoreanPreprocessor  | 기존 로직 전체 |

동일 질문셋으로 검색 결과 비교 → 실제 차이 측정

---

## 참고 자료

- [AWS Nori 플러그인](https://aws.amazon.com/ko/blogs/tech/amazon-opensearch-service-korean-nori-plugin-for-analysis/)
- [Nori 형태소 분석기](https://esbook.kimjmin.net/06-text-analysis/6.7-stemming/6.7.2-nori)
- [OpenAI 임베딩 전처리](https://community.openai.com/t/preprocessing-for-embeddings/295017)
- [kiwipiepy PyPI](https://pypi.org/project/kiwipiepy/)
- [RAG 전처리 베스트 프랙티스](https://chamomile.ai/reliable-rag-with-data-preprocessing/)

---

## 파일

- `src/rag/preprocessor.py`
- `tests/test_preprocessor.py`

---

## 할 일

- [ ] Protocol 정의
- [ ] NoopPreprocessor 구현
- [ ] MinimalPreprocessor 구현 (선택)
- [ ] 파이프라인 완성 후 효과 비교 테스트
