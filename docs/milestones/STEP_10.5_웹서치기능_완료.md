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

## 2. 검색 vs 크롤링 차이점

### 2.1 개념 비교

| 항목 | 검색 (Search) | 크롤링 (Extract/Crawl) |
|------|---------------|------------------------|
| **반환 내용** | 검색 결과 목록 (제목, snippet, URL) | 페이지 전체 콘텐츠 |
| **snippet 길이** | ~150자 정도 | 전체 본문 |
| **페이지 접속** | ❌ 안함 | ✅ 직접 접속해서 추출 |
| **용도** | "어디에 정보가 있는지" 찾기 | "정보 자체" 가져오기 |
| **비용** | 저렴 | 상대적으로 비쌈 |

### 2.2 예시: "한국 근로기준법 연차휴가" 검색

#### Google CSE (검색만)
```json
{
  "title": "근로기준법 - 국가법령정보센터",
  "snippet": "제60조(연차 유급휴가) ① 사용자는 1년간 80퍼센트 이상 출근한 근로자에게 15일의 유급휴가를...",
  "link": "https://law.go.kr/..."
}
```
→ **snippet만** 받음 (150자 정도로 잘림)

#### Tavily Extract / 크롤링
```
제60조(연차 유급휴가)
① 사용자는 1년간 80퍼센트 이상 출근한 근로자에게 15일의 유급휴가를 주어야 한다.
② 사용자는 계속하여 근로한 기간이 1년 미만인 근로자...
③ ...
(전체 조문 내용)
```
→ **페이지 전체 내용** 받음

### 2.3 Level 4 질문에 snippet만으로 충분한가?

| 질문 | CSE snippet | 크롤링 필요? |
|------|-------------|-------------|
| 근로기준법 연차 규정 | △ 대략적 내용 가능 | 정확한 조문 필요시 ✅ |
| Slack/Notion 기능 비교 | △ 여러 결과 snippet 조합 | 상세 비교시 ✅ |
| IT 트렌드 | ○ 개요 수준 가능 | 대부분 불필요 |
| 원격근무 법규 변경 | △ 뉴스 헤드라인 수준 | 상세 내용 필요시 ✅ |

**결론**: snippet만으로 어느 정도 답변 가능하지만, 정확한 정보가 필요하면 크롤링 추가 권장

### 2.4 서비스별 제공 기능

| 서비스 | Search (검색) | Extract (크롤링) |
|--------|--------------|------------------|
| **Tavily** | ✅ tavily_search | ✅ tavily_extract |
| **Google CSE** | ✅ | ❌ (별도 구현 필요) |
| **Exa** | ✅ exa_search | ✅ exa_get_contents |
| **Serper.dev** | ✅ | ❌ |

---

## 3. 웹 검색 API 후보 비교

### 3.1 후보 목록

| 서비스 | 무료 티어 | 유료 단가 | Strands 통합 | 특징 |
|--------|-----------|-----------|--------------|------|
| **Tavily** | 1,000회/월 | ~11원/회 ($0.008) | ✅ 기본 제공 | AI 에이전트 최적화, RAG에 최적 |
| **Google CSE** | 100회/일 (~3,000/월) | ~7원/회 ($0.005) | ❌ 직접 구현 | GCP 크레딧 활용 가능 |
| **Serper.dev** | 2,500회/월 | 미확인 | ❌ 직접 구현 | Google 검색 결과 JSON 반환 |
| **Exa** | 제한적 | 유료 | ✅ 기본 제공 | Neural + Keyword 하이브리드 |
| **DuckDuckGo** | 무제한 (rate limit) | 무료 | ❌ 직접 구현 | API 키 불필요, 불안정 |

### 3.2 상세 비용 분석

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

### 3.3 장단점 비교

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

## 4. 구현 방법

### 4.1 Option A: Tavily 사용 (권장 - 빠른 구현)

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

### 4.2 Option B: Google CSE 직접 구현 (GCP 크레딧 활용)

#### 4.2.1 사전 설정

1. [Google Cloud Console](https://console.cloud.google.com/) → API 활성화
2. [Programmable Search Engine](https://programmablesearchengine.google.com/) → 검색 엔진 생성
3. API 키 발급

**환경변수:**
```
GOOGLE_API_KEY=AIzaSy...
GOOGLE_CSE_ID=a1b2c3d4...
```

#### 4.2.2 도구 구현

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

#### 4.2.3 LangChain 래퍼 활용 (대안)

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

### 4.3 Option C: Exa 사용

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

### 4.4 Option D: Google CSE + 크롤러 조합 (검색 + 페이지 추출)

Google CSE는 검색만 제공하므로, 페이지 전체 내용이 필요하면 별도 크롤러 추가:

```python
from strands import tool
import httpx
from bs4 import BeautifulSoup

@tool
def fetch_page(url: str) -> str:
    """
    웹 페이지의 본문 내용을 추출합니다.

    Args:
        url: 추출할 페이지 URL

    Returns:
        페이지 본문 텍스트
    """
    response = httpx.get(url, follow_redirects=True, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    # 불필요한 태그 제거
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    # 본문 텍스트 추출
    text = soup.get_text(separator="\n", strip=True)

    # 길이 제한 (토큰 절약)
    return text[:5000] if len(text) > 5000 else text
```

**추가 설치:**
```bash
pip install beautifulsoup4
```

---

## 5. 결정 포인트

### 5.1 선택 기준

| 우선순위 | 추천 |
|----------|------|
| 빠른 구현 | Tavily |
| GCP 크레딧 활용 | Google CSE |
| 무료 최대화 | Google CSE (3,000/월) 또는 Serper (2,500/월) |
| 결과 품질 | Tavily (AI 최적화) |

### 5.2 현재 상황

- GCP 무료 크레딧 보유 → **Google CSE 유력**
- 테스트 목적 (Level 4 질문 4개) → 무료 티어로 충분

### 5.3 추천 조합

| 요구사항 | 추천 |
|----------|------|
| 검색만 필요 (snippet 충분) | Google CSE |
| 검색 + 페이지 추출 필요 | Google CSE + fetch_page |
| 빠른 구현 + 둘 다 필요 | Tavily (search + extract) |

---

## 6. 구현 계획

### Phase 1: Google CSE 도구 구현
- [ ] `src/agent/tools/web_search.py` 생성
- [ ] Google API 키 및 CSE ID 설정
- [ ] 기본 검색 기능 구현

### Phase 2: 크롤러 도구 구현 (선택)
- [ ] `src/agent/tools/fetch_page.py` 생성
- [ ] BeautifulSoup 기반 본문 추출
- [ ] 길이 제한 및 에러 핸들링

### Phase 3: Agent 통합
- [ ] `UnifiedAgent`에 web_search (+ fetch_page) 도구 추가
- [ ] Level 4 질문용 프롬프트 조정

### Phase 4: 테스트
- [ ] Level 4 질문 4개 테스트
- [ ] 비용 모니터링

---

## 7. 수정 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/agent/tools/web_search.py` | 신규 - 웹 검색 도구 |
| `src/agent/tools/fetch_page.py` | 신규 - 페이지 크롤링 도구 (선택) |
| `src/agent/unified_agent.py` | web_search (+ fetch_page) 도구 추가 |
| `.env` | GOOGLE_API_KEY, GOOGLE_CSE_ID 추가 |
| `requirements.txt` | httpx, beautifulsoup4 추가 |

---

## 8. Tavily 비용 최적화 (참고)

### 8.1 크레딧 소모 구조

| 옵션 | 크레딧 |
|------|--------|
| `search_depth="basic"` | 1 크레딧 |
| `search_depth="advanced"` | 2 크레딧 |
| `auto_parameters=True` (기본값) | 자동으로 advanced 선택될 수 있음 |
| `include_answer=True` | 추가 비용 가능 |

### 8.2 비용 절감 방법

커스텀 래퍼로 기본값 조정:

```python
from strands import tool
from tavily import TavilyClient
import os

@tool
def web_search(query: str) -> str:
    """외부 웹 검색을 수행합니다. (비용 최적화)"""
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    result = client.search(
        query=query,
        search_depth="basic",      # 1 크레딧 (기본 advanced는 2)
        max_results=5,             # 기본 10 → 5
        include_answer=False,      # LLM 답변 생성 안함
        auto_parameters=False,     # 자동 파라미터 비활성화
    )

    # 결과 포맷팅
    results = []
    for r in result.get("results", []):
        results.append(f"- {r['title']}: {r['content'][:200]}...")
    return "\n".join(results) if results else "검색 결과가 없습니다."
```

### 8.3 예상 절감 효과

| 설정 | 호출당 크레딧 | 월 1,000회 기준 |
|------|--------------|----------------|
| 기본 (auto, advanced) | 2~3 | 2,000~3,000 크레딧 |
| 최적화 (basic, no answer) | 1 | 1,000 크레딧 |

→ **50~66% 비용 절감 가능**

---

## 9. 참고 자료

- [Google Custom Search JSON API](https://developers.google.com/custom-search/v1/overview)
- [Programmable Search Engine 설정](https://programmablesearchengine.google.com/)
- [Tavily 공식 문서](https://docs.tavily.com/)
- [Strands Tools GitHub](https://github.com/strands-agents/tools)
- [LangChain Google Search](https://python.langchain.com/docs/integrations/tools/google_search/)
