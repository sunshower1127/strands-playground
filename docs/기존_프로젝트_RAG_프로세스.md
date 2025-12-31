## 1. OpenSearch 하이브리드 검색 쿼리 (KNN + BM25 조합)

하이브리드 검색 쿼리는 `create_hybrid_search_query` 함수에서 구성됩니다:

```538:683:app/router/vector/opensearch.py
def create_hybrid_search_query(
    query: str,
    query_embedding: List[float],
    top_k: int,
    must_filters: List[dict] = None,
    enable_knn: bool = True
) -> dict:
    processed_query = _remove_korean_particles(query) or query
    if processed_query != query:
        print(f"🔍 한국어 조사 제거: '{query}' → '{processed_query}'")

    # 토큰 수 기반으로 minimum_should_match 동적 계산
    toks = [t for t in re.findall(r'[\w가-힣]+', processed_query) if t]
    n = len(toks)
    # 동적 MSM: 매우 짧은 질의는 완화
    if n <= 1:
        msm = 1
    elif n == 2:
        msm = 1
    elif n in (3, 4):
        msm = 2
    else:
        msm = max(1, int(round(n * 0.6)))

    subqueries = []

    # 1) 텍스트(본문/제목) 전용 multi_match with 최신성 보너스
    text_bool = {
        "function_score": {
            "query": {
                "bool": {
                    "must": [{
                        "multi_match": {
                            "query": processed_query,
                            "fields": [
                                "chunk_text^4.0", # 주 텍스트 필드 (실제 데이터 있음)
                                "text.ko^3.5",    # 한국어 text (실제 데이터 있음)
                                "text.en^1.8"     # 영어 text (실제 데이터 있음)
                            ],
                            "type": "cross_fields",
                            "operator": "OR",
                            "minimum_should_match": str(msm)
                        }
                    }],
                    "should": [],
                }
            },
            "functions": [
                {
                    "gauss": {
                        "metadata.last_modified_at": {
                            "origin": "now",
                            "scale": "180d",  # 180일(6개월) 기준으로 확장
                            "decay": 0.8,     # 부드러운 감쇠 유지
                            "offset": "7d"    # 7일 이내는 최대 점수
                        }
                    },
                    "weight": 0.25  # 전체 텍스트 점수의 25% 정도만 영향
                }
            ],
            "score_mode": "multiply",  # 곱셈으로 더 자연스럽게
            "boost_mode": "multiply"   # 원점수 * (1 + 최신성보너스*weight)
        }
    }

    # 2) 간단한 bigram phrase 부스트 (본문/제목만) - function_score 내부 bool에 추가
    bigrams = set(" ".join(toks[i:i+2]) for i in range(len(toks)-1))
    for p in bigrams:
        text_bool["function_score"]["query"]["bool"]["should"].append({
            "match_phrase": {"text.ko":  {"query": p, "slop": 1, "boost": 3.5}}
        })
        text_bool["function_score"]["query"]["bool"]["should"].append({
            "match_phrase": {"title.ko": {"query": p, "slop": 1, "boost": 2.8}}
        })

    # 3) 파일명/소스 경로 부스트 (매핑 변경 전 임시 안전안)
    #    - 유니코드 NFKC/NFD 모두 사용
    #    - leading wildcard(*term*)는 비용이 크므로 boost는 낮게
    fn_variants = set()
    for v in {unicodedata.normalize("NFKC", processed_query), unicodedata.normalize("NFD", processed_query)}:
        fn_variants.add(v)
        fn_variants.add(v.replace(" ", ""))
        fn_variants.add(v.replace(" ", "_"))

    for v in fn_variants:
        # 다양한 파일명 필드에 대해 검색 (wildcard/prefix 부스트 감소)
        for field_name in ["file_name", "fileName", "original_filename"]:
            text_bool["function_score"]["query"]["bool"]["should"].append({
                "wildcard": {field_name: {"value": f"*{v}*", "boost": 1.2}}  # 2.2 → 1.2
            })
            # 접두 prefix 부스트도 감소
            if len(v) >= 3:
                text_bool["function_score"]["query"]["bool"]["should"].append({
                    "prefix": {field_name: {"value": v[:3], "boost": 1.5}}  # 2.5 → 1.5
                })

    if must_filters:
        text_bool["function_score"]["query"]["bool"]["filter"] = must_filters

    subqueries.append(text_bool)
    print("✅ 텍스트 검색: cross_fields(OR+MSM) + phrase 부스트 + 파일명 wildcard/prefix 부스트 적용")

    # 4) 벡터(semantic) - RRF window와 정합
    if enable_knn and query_embedding:
        k_value = OpenSearchConfig.RRF_WINDOW_SIZE  # RRF window와 동일하게 설정
        knn_q = {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": k_value,
                    "boost": 0.7
                }
            }
        }
        if must_filters:
            knn_q["knn"]["embedding"]["filter"] = {"bool": {"filter": must_filters}}
        subqueries.append(knn_q)
        print(f"✅ KNN 벡터 검색 추가 (k={k_value}, dim={len(query_embedding)})")
    else:
        print("⚠️ KNN 벡터 검색 비활성화")

    # 하이브리드 검색 쿼리 구성 (function_score는 개별 subquery에 이미 적용됨)
    hybrid_query = {
        "size": top_k,
        "_source": {
            "excludes": ["vector", "text_vector", "embedding"]
        },
        "query": {
            "hybrid": {
                "queries": subqueries,
                # 텍스트 서브쿼리 후보 수 확대로 RRF 합산 개선 (OpenSearch 2.19+)
                "pagination_depth": max(100, top_k * 4)
            }
        },
        "sort": [
            "_score"  # 하이브리드 검색 점수로 정렬
        ]
    }

    print("🔍 하이브리드 검색 구성 완료:")
    print(f"  - 결과 크기: {top_k}")
    print(f"  - 필터 조건: {len(must_filters) if must_filters else 0}개")
    print(f"  - 텍스트 검색: 최신성 보너스 적용 (180일 기준, 25% 가중치)")
    print(f"  - 벡터 검색: 순수 의미적 유사도")
    print(f"  - 최종 정렬: 하이브리드 점수 (관련성 + 최신성 균형)")
    return hybrid_query
```

## 2. 검색 파라미터 (k값, boost, threshold)

검색 파라미터는 여러 위치에 정의되어 있습니다:

### KNN 파라미터

```33:45:app/router/vector/opensearch.py
class OpenSearchConfig:
    """OpenSearch 관련 설정값들"""
    KNN_EF_SEARCH = 100
    KNN_EF_CONSTRUCTION = 200
    VECTOR_DIMENSION = 1024
    NUMBER_OF_SHARDS = 1
    NUMBER_OF_REPLICAS = 2
    REFRESH_INTERVAL = "1s"
    HYBRID_RRF_PIPELINE = "hybrid-rrf"
    HYBRID_RRF_PIPELINE_V2 = "hybrid-rrf-tuned"
    RRF_WINDOW_SIZE = 100
    RRF_RANK_CONSTANT = 20
    MAX_KNN_DOCS_THRESHOLD = 5000
```

### Boost 값들

```607:648:app/router/vector/opensearch.py
        text_bool["function_score"]["query"]["bool"]["should"].append({
            "match_phrase": {"text.ko":  {"query": p, "slop": 1, "boost": 3.5}}
        })
        text_bool["function_score"]["query"]["bool"]["should"].append({
            "match_phrase": {"title.ko": {"query": p, "slop": 1, "boost": 2.8}}
        })
    # ... 중략 ...
            text_bool["function_score"]["query"]["bool"]["should"].append({
                "wildcard": {field_name: {"value": f"*{v}*", "boost": 1.2}}  # 2.2 → 1.2
            })
            # 접두 prefix 부스트도 감소
            if len(v) >= 3:
                text_bool["function_score"]["query"]["bool"]["should"].append({
                    "prefix": {field_name: {"value": v[:3], "boost": 1.5}}  # 2.5 → 1.5
                })
    # ... 중략 ...
        knn_q = {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": k_value,
                    "boost": 0.7
                }
            }
        }
```

### Threshold 값들

```1952:2003:app/router/vector/opensearch.py
def adaptive_score_analysis(scores: List[float]) -> dict:
    """
    하이브리드(RRF) 점수 분포를 상대 기준으로 분석해 임계값을 정한다.
    - 점수 스케일(0.01~0.05 등)에 무관하게 작동
    - 최소 보존 개수 보장
    """
    if not scores:
        return {"threshold": 0.0, "method": "no_results", "keep_min": 1}

    s = sorted(scores, reverse=True)
    n = len(s)
    max_s = s[0]

    # 0으로 나누기 방지
    if max_s <= 0:
        return {"threshold": 0.0, "method": "all_zero", "keep_min": 1}

    # 1) 정규화 점수(상대 스케일)
    sn = [x / max_s for x in s]  # [1.0, ..., 0.xxx]

    # 2) 엘보우(최대 갭) 탐지
    gaps = [(sn[i] - sn[i+1]) for i in range(n - 1)]
    elbow_thr = sn[-1]
    if gaps:
        gi = max(range(len(gaps)), key=lambda j: gaps[j])
        elbow_thr = sn[gi+1]  # 엘보우 뒤쪽 값

    # 3) 분위수 기반 - 설정 가능한 백분위수
    QUANTILE_PERCENTAGE = 0.15  # 상위 15% (완화: 0.2 → 0.15)
    q_idx = max(1, int(n * QUANTILE_PERCENTAGE))
    q_thr = sn[q_idx] if q_idx < n else sn[-1]

    # 4) 혼합 임계값 (클램프) - 설정 가능한 상한/하한
    THRESHOLD_UPPER_BOUND = 0.9
    THRESHOLD_LOWER_BOUND = 0.1
    thr_rel = max(min(max(elbow_thr, q_thr), THRESHOLD_UPPER_BOUND), THRESHOLD_LOWER_BOUND)

    # 5) 절대 스코어 임계값으로 환산
    thr_abs = thr_rel * max_s

    # 6) 최소 보존 개수 - 설정 가능한 값들
    MIN_KEEP_COUNT = 3
    MAX_KEEP_COUNT = 8
    KEEP_PERCENTAGE = 0.1
    keep_min = min(MAX_KEEP_COUNT, max(MIN_KEEP_COUNT, int(n * KEEP_PERCENTAGE)))

    return {
        "threshold": thr_abs,
        "method": "hybrid_elbow_quantile",
        "keep_min": keep_min,
        "max_score": max_s
    }
```

## 3. 임베딩 전처리 (텍스트 정규화)

한국어 쿼리 전처리는 `_remove_korean_particles` 함수에서 수행됩니다:

```495:535:app/router/vector/opensearch.py
def _remove_korean_particles(query: str) -> str:
    """
    한국어 쿼리 전처리 (Nori 토크나이저 보완용)

    Nori가 처리하지 못하는 영역만 담당:
    - 문장 종결어미 제거 (알려줘, 해주세요 등)
    - 숫자 단위 정규화 (2020년 → 2020)
    - 문장부호 정리

    Note: 기본 조사(이/가/을/를)는 Nori POS 필터가 처리하므로 제외
    """
    if not query:
        return query

    # 1) 유니코드 정규화 + 양끝 문장부호/공백 정리
    s = unicodedata.normalize('NFKC', query).strip()
    punct_pattern = re.compile(r'^[\s"""\'''\(\)\[\]\{\},.?!:;~·…<>]+|[\s"""\'''\(\)\[\]\{\},.?!:;~·…<>]+$')
    s = punct_pattern.sub('', s)

    # 2) 문장 종결어미 제거 (Nori가 처리하지 못하는 복합 어미)
    ending_pattern = re.compile(
        r'(?:'
        r'(?:알|보|찾|설명|검색|가르쳐|말|정리|요약|조회|제출|추천|비교|분석)해?줘(?:요)?'
        r'|해\s?주세요|해주세요|주세요'
        r'|해줘|해라|해$'
        r'|인가요\??|인가\??|이야\??|야\??'
        r')$'
    )

    # 반복 제거 (중첩된 어미 처리)
    for _ in range(2):
        ns = ending_pattern.sub('', s).strip()
        if ns == s:
            break
        s = ns

    # 3) 숫자 단위 정규화 (검색 최적화)
    year_pattern = re.compile(r'(\d{2,4})\s*년\b')
    s = year_pattern.sub(r'\1', s)

    return s
```

## 4. LLM 프롬프트 템플릿 (context 주입 방식)

프롬프트 템플릿은 `app/config/prompts.py`에 정의되어 있습니다:

````85:161:app/config/prompts.py
RAG_SYSTEM_PROMPT = """
You are a professional AI assistant powered by an advanced document search system. You must provide only accurate and reliable information based on provided documents.

🔍 **Search System Features:**
- Hybrid Search: Vector similarity + text matching combination
- Adaptive Quality Filtering: Statistical analysis to select only highly relevant documents
- Permission-based Security: Search only user-accessible documents
- Real-time Click Navigation: Precise document navigation via md5_hash

📚 **Core Principles:**
- Answer ONLY based on provided document content
- NEVER guess or generate information not in documents
- Admit honestly when information is uncertain or insufficient
- **CRITICAL: RESPOND IN THE SAME LANGUAGE AS THE USER'S QUESTION (한국어 질문 → 한국어 답변, English → English)**
- **Always cite source (document name, page number) for each piece of information**

⚠️ **Prohibited Actions:**
- Supplementing answers with general knowledge or speculation
- Presenting undocumented content as fact
- Over-expanding or inferring beyond document content
- Omitting page numbers or source information

📝 **Response Format (Must Follow):**

**Response Format (Match User's Language - 사용자 언어와 동일하게):**
```markdown
📚 **문서 기반 답변** (for Korean questions / 한국어 질문)
📚 **Document-Based Answer** (for English questions / 영어 질문)

## [Document-based Information]
[Primary answer with EXACT clickable inline links from context: [[1]](navigate://...), [[2]](navigate://...)]

## [Additional Context] (if needed for follow-up questions)
[Information from previous conversation context, clearly marked as such]

**📚 참고문서:**
- [📄 문서 (p.X)](navigate://document?md5_hash={hash}&page={page})
- [📄 문서 (p.Y)](navigate://document?md5_hash={hash}&page={page})

Example:
- Document-based: "The XYZ feature works as follows**[[1]](navigate://document?...)**. This is further explained**[[2]](navigate://...)**."
- Conversation context: "Based on our previous discussion about ABC, this relates to..."
````

**When No Search Results or No Project Selected:**

- Use "📋 **Document Search Results**" header and English guidance only

**🔗 Reference Document Link Usage:**

- System automatically generates clickable links
- Link format: `[📄 Document (p.X)](navigate://document?md5_hash={hash}&page={page})`
- MUST use system-provided links exactly as given
- NEVER modify or create links manually

**🔍 Source Citation Rules:**

- **Use the EXACT clickable inline links provided in the context**: The system provides links like `[[1]](navigate://document?...)`
- **COPY these links exactly as provided** and place them immediately after relevant information
- Example: "The capital is Seoul**[[1]](navigate://document?md5_hash=...&page=1)**"
- **NEVER create your own links** - always use the links provided in the document context
- **NEVER modify the link format** - copy and paste the exact `[[N]](navigate://...)` format
- **ALWAYS include a "📚 참고문서:" (Reference Documents) section at the end** with the full document links
- Reference section format: `- [📄 문서 (p.X)](navigate://...)` (without numbered prefix)
- **All responses must match the user's question language**

**📊 Quality Assurance:**

- Adaptive filtering provides only highly relevant documents
- Score distribution analysis ensures precise document selection
- User permissions ensure access to authorized documents only

**🌍 Language Policy:**

- **ALL responses must match the user's question language**
- Korean question → Korean response
- English question → English response
- German question → German response
- Any language question → Same language response

Always respond professionally in the user's question language while prioritizing document reliability, source citation, and providing clickable reference links.
"""

````

## 5. project_id 필터링 로직

프로젝트 필터링은 `get_accessible_document_ids`와 `execute_chat_search`에서 처리됩니다:

```839:871:app/router/vector/opensearch.py
async def get_accessible_document_ids(session: AsyncSession, user_id: int, project_id: int) -> List[int]:
    """
    사용자가 특정 프로젝트에서 접근 가능한 document_id 목록을 조회

    로직:
    1. ProjectDocuments에서 특정 프로젝트(project_id)의 문서들을 찾고
    2. UserDocumentAccess와 INNER JOIN하여 사용자(user_id) 권한이 있는 문서만 필터링
    3. 두 테이블 모두에서 삭제되지 않은(deleted_at IS NULL) 레코드만 반환
    4. 중복 제거(DISTINCT)하여 고유한 document_id만 반환
    """
    # INNER JOIN으로 프로젝트 소속 + 사용자 권한 모두 만족하는 문서 조회
    query = select(ProjectDocuments.document_id).join(
        UserDocumentAccess,
        ProjectDocuments.document_id == UserDocumentAccess.document_id
    ).where(
        ProjectDocuments.project_id == project_id,
        UserDocumentAccess.user_id == user_id,
        ProjectDocuments.deleted_at.is_(None),
        UserDocumentAccess.deleted_at.is_(None)
    ).distinct()

    result = await session.execute(query)
    document_ids = [row[0] for row in result.fetchall()]

    if document_ids:
        print(f"✅ 조회된 접근 가능한 문서 ID: {len(document_ids)}개 (user_id={user_id}, project_id={project_id})")
        print(f"📋 Document IDs: {document_ids}")

    else:
        print(f"⚠️ 접근 가능한 문서가 없습니다 (user_id={user_id}, project_id={project_id})")
        print(f"💡 확인사항: 1) 프로젝트에 문서가 있는지 2) 사용자에게 해당 문서 권한이 있는지")

    return document_ids
````

검색 실행 시 필터링 적용:

```914:952:app/router/vector/opensearch.py
        # 데이터베이스에서 접근 가능한 document_id 목록 조회
        accessible_document_ids = await get_accessible_document_ids(session, user_id, project_id)

        if not accessible_document_ids:
            print(f"⚠️ 접근 가능한 문서가 없습니다: user_id={user_id}, project_id={project_id}")
            return SearchResponse(results=[], total_count=0)

        print(f"🔍 DEBUG - 검색 파라미터:")
        print(f"  - top_k: {top_k}")
        print(f"  - accessible_document_ids: {len(accessible_document_ids)}개")
        print(f"  - query: '{query}'")
        print(f"  - user_id: {user_id}, project_id: {project_id}")

        # 🎯 태그된 문서 처리 - 검색 범위 제한
        if tagged_document_ids:
            # 태그된 문서가 접근 가능한지 확인
            valid_tagged_docs = [doc_id for doc_id in tagged_document_ids if doc_id in accessible_document_ids]

            if valid_tagged_docs:
                print(f"📎 태그된 문서만 검색: {len(valid_tagged_docs)}개")
                print(f"   Document IDs: {valid_tagged_docs}")
                # 🎯 태그된 문서로만 검색 범위 제한
                search_document_ids = valid_tagged_docs
            else:
                print(f"⚠️ 태그된 문서가 접근 권한 내에 없음 - 전체 검색으로 대체")
                search_document_ids = accessible_document_ids
        else:
            print(f"🔍 전체 프로젝트 검색 (태그된 문서 없음)")
            search_document_ids = accessible_document_ids

        # 필터 조건 구성 (검색 범위로 제한)
        must_filters = [
            {
                'terms': {
                    'document_id': search_document_ids
                }
            }
        ]
```

---

요약:

- 하이브리드 검색: KNN 벡터 검색 + 텍스트 검색(BM25)을 RRF로 결합
- 파라미터: KNN k=100, boost 값들(텍스트 3.5~4.0, 벡터 0.7), 동적 threshold 계산
- 전처리: 한국어 조사/어미 제거, 유니코드 정규화
- 프롬프트: 문서 기반 답변 강제, 출처 명시, 클릭 가능한 링크 사용
- 필터링: ProjectDocuments와 UserDocumentAccess JOIN으로 권한 기반 필터링
