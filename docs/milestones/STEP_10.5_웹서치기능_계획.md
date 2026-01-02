# STEP 10.5: 웹서치 기능 계획

## 목표
Level 4 질문(multi_tool 카테고리)을 위한 웹 검색 도구 추가

---

## 1. 배경

### 1.1 Level 4 질문 요구사항

`question_set.json`의 Level 4 질문들 (id 15~18):

| ID | 질문 | 필요 도구 |
|----|------|-----------|
| 15 | 우리 휴가 정책이 한국 근로기준법에 맞는가? | document_search + **web_search** |
| 16 | FlowSync와 Slack/Notion 기능 비교해줘 | document_search + **web_search** |
| 17 | 2024 IT 트렌드 중 우리 로드맵에 반영된 것은? | document_search + **web_search** |
| 18 | 원격근무 관련 최신 법규 변경사항이 우리 정책에 영향 있나? | document_search + **web_search** |

→ 내부 문서 검색 + 외부 웹 검색이 함께 필요

---

## 2. 웹 검색 API 후보 비교

### 2.1 후보 목록

| 서비스 | 무료 티어 | 유료 단가 | Strands 통합 | 특징 |
|--------|-----------|-----------|--------------|------|
| **Tavily** | 1,000회/월 | ~11원/회 ($0.008) | ✅ 기본 제공 | AI 에이전트 최적화, RAG에 최적 |
| **Google CSE** | 100회/일 (~3,000/월) | ~7원/회 ($0.005) | ❌ 직접 구현 | GCP 크레딧 활용 가능 |
| **Serper.dev** | 2,500회/월 | 미확인 | ❌ 직접 구현 | Google 검색 결과 JSON 반환 |
| **Exa** | 제한적 | 유료 | ✅ 기본 제공 | Neural + Keyword 하이브리드 |
| **DuckDuckGo** | 무제한 (rate limit) | 무료 | ❌ 직접 구현 | API 키 불필요, 불안정 |

### 2.2 상세 비용 분석

#### Tavily 요금제

| 플랜 | 가격 | 크레딧 | 크레딧당 단가 |
|------|------|--------|---------------|
| Researcher (Free) | 무료 | 1,000/월 | - |
| Project | $30/월 | 4,000/월 | $0.0075 (~10.5원) |
| Bootstrap | $100/월 | 15,000/월 | $0.0067 (~9.3원) |
| Pay-As-You-Go | 초과분만 | - | $0.008 (~11원) |

#### Google Custom Search API

| 항목 | 내용 |
|------|------|
| 무료 | 100회/일 (≈3,000회/월) |
| 유료 | $5 / 1,000 쿼리 (~7원/회) |
| 일일 한도 | 최대 10,000회/일 |
| 장점 | **GCP 무료 크레딧 활용 가능** |

#### 질문당 예상 비용

| 서비스 | 1회 검색 | 2회 검색 | 3회 검색 |
|--------|----------|----------|----------|
| Tavily (PAYG) | ~11원 | ~22원 | ~33원 |
| Tavily (Bootstrap) | ~9원 | ~19원 | ~28원 |
| Google CSE | ~7원 | ~14원 | ~21원 |

### 2.3 장단점 비교

#### Tavily
**장점:**
- Strands에 `strands_tools.tavily_search`로 기본 제공
- AI 에이전트 최적화 (깨끗한 결과, 노이즈 제거)
- 설정 간단 (API 키만 발급)

**단점:**
- 유료 (무료 1,000회/월)
- GCP 크레딧 활용 불가

#### Google Custom Search API
**장점:**
- 무료 티어 넉넉 (3,000회/월)
- **GCP 무료 크레딧 활용 가능**
- 단가 저렴 (~30% 저렴)

**단점:**
- Strands 기본 도구 없음 (직접 구현 필요)
- 설정 복잡 (Search Engine ID + API 키)
- 결과 파싱 직접 처리

#### Serper.dev
**장점:**
- 무료 2,500회/월
- Google 검색 결과 그대로

**단점:**
- Strands 통합 없음
- 문서/커뮤니티 적음

---

## 3. 구현 방법

### 3.1 Option A: Tavily 사용 (권장 - 빠른 구현)

```bash
pip install 'strands-agents-tools[tavily]'
```

```python
from strands import Agent
from strands_tools import tavily_search

agent = Agent(tools=[search_documents, tavily_search])
```

**환경변수:**
```
TAVILY_API_KEY=tvly-xxxxx
```

### 3.2 Option B: Google CSE 직접 구현 (GCP 크레딧 활용)

#### 3.2.1 사전 설정

1. [Google Cloud Console](https://console.cloud.google.com/) → API 활성화
2. [Programmable Search Engine](https://programmablesearchengine.google.com/) → 검색 엔진 생성
3. API 키 발급

**환경변수:**
```
GOOGLE_API_KEY=AIzaSy...
GOOGLE_CSE_ID=a1b2c3d4...
```

#### 3.2.2 도구 구현

```python
from strands import tool
import httpx

@tool
def web_search(query: str) -> str:
    """
    Google에서 웹 검색을 수행합니다.

    Args:
        query: 검색할 키워드

    Returns:
        검색 결과 요약
    """
    api_key = os.environ["GOOGLE_API_KEY"]
    cse_id = os.environ["GOOGLE_CSE_ID"]

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": 5,  # 상위 5개 결과
    }

    response = httpx.get(url, params=params)
    data = response.json()

    # 결과 포맷팅
    results = []
    for item in data.get("items", []):
        results.append(f"- {item['title']}: {item['snippet']}")

    return "\n".join(results) if results else "검색 결과가 없습니다."
```

#### 3.2.3 LangChain 래퍼 활용 (대안)

```python
from strands import tool
from langchain_google_community import GoogleSearchAPIWrapper

search_wrapper = GoogleSearchAPIWrapper()

@tool
def web_search(query: str) -> str:
    """Google에서 웹 검색을 수행합니다."""
    return search_wrapper.run(query)
```

**추가 설치:**
```bash
pip install langchain-google-community google-api-python-client
```

### 3.3 Option C: Exa 사용

```python
from strands import Agent
from strands_tools import exa_search

agent = Agent(tools=[search_documents, exa_search])
```

**환경변수:**
```
EXA_API_KEY=exa-xxxxx
```

---

## 4. 결정 포인트

### 4.1 선택 기준

| 우선순위 | 추천 |
|----------|------|
| 빠른 구현 | Tavily |
| GCP 크레딧 활용 | Google CSE |
| 무료 최대화 | Google CSE (3,000/월) 또는 Serper (2,500/월) |
| 결과 품질 | Tavily (AI 최적화) |

### 4.2 현재 상황

- GCP 무료 크레딧 보유 → **Google CSE 유력**
- 테스트 목적 (Level 4 질문 4개) → 무료 티어로 충분

---

## 5. 구현 계획

### Phase 1: Google CSE 도구 구현
- [ ] `src/agent/tools/web_search.py` 생성
- [ ] Google API 키 및 CSE ID 설정
- [ ] 기본 검색 기능 구현

### Phase 2: Agent 통합
- [ ] `UnifiedAgent`에 web_search 도구 추가
- [ ] Level 4 질문용 프롬프트 조정

### Phase 3: 테스트
- [ ] Level 4 질문 4개 테스트
- [ ] 비용 모니터링

---

## 6. 수정 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/agent/tools/web_search.py` | 신규 - 웹 검색 도구 |
| `src/agent/unified_agent.py` | web_search 도구 추가 |
| `.env` | GOOGLE_API_KEY, GOOGLE_CSE_ID 추가 |
| `requirements.txt` | httpx 또는 langchain-google-community 추가 |

---

## 7. 참고 자료

- [Google Custom Search JSON API](https://developers.google.com/custom-search/v1/overview)
- [Programmable Search Engine 설정](https://programmablesearchengine.google.com/)
- [Tavily 공식 문서](https://docs.tavily.com/)
- [Strands Tools GitHub](https://github.com/strands-agents/tools)
- [LangChain Google Search](https://python.langchain.com/docs/integrations/tools/google_search/)
