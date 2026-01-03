# STEP CG: 프롬프트 템플릿 (PromptTemplate)

## 상태: 완료 ✅

## 목표
컨텍스트 + 질문 + 언어 설정 → LLM 프롬프트 생성

---

## 조사 결과 요약

### 직접 구현 필요 여부
OpenSearch RAG Tool은 프롬프트를 LLM에 전달하는 역할만 함.
**출처 명시, 할루시네이션 방지** 로직은 프롬프트에서 직접 구현해야 함.
→ **직접 구현 권장**

### 외부 라이브러리 비교
| 라이브러리 | 장점 | 단점 |
|-----------|------|------|
| LangChain | 체인 파이프라인, 대화 히스토리 | 의존성 무거움, 오버킬 |
| LlamaIndex | Jinja2 문법, 리파인먼트 | 검색/인덱싱 특화, 과함 |

→ **단순 문자열 포매팅으로 충분** (외부 의존성 불필요)

### 할루시네이션 방지 (2025 연구)
- RAG + 명시적 지시로 **42-68% 할루시네이션 감소** 가능
- 핵심 패턴: `"answer based only on the provided documents"`
- 권장: 출처 형식 명시 `[문서명]`, 답변 불가 시 행동 명시

### 다국어 프롬프트 전략 (2025 연구)

#### 언어별 성능 차이
| 상황 | 권장 언어 | 성능 차이 |
|------|----------|----------|
| 추론/수학 문제 | 영어 | 영어가 ~37% 더 좋음 |
| 정보 추출 (RAG) | 콘텐츠 언어 매칭 | 매칭 시 더 정확 |
| 문화적 맥락 | 해당 문화권 언어 | 할루시네이션 감소 |
| 처리 속도 | 영어 | 비영어 25-35% 더 느림 |

#### 권장: 하이브리드 접근
```
System Prompt: 영어 (추론 성능 최적화)
Context: 원본 언어 유지 (번역 손실 방지)
User Query: 사용자 언어 그대로
응답 언어: 명시적 지시 필수
```

#### LLM API 언어 파라미터
**모든 주요 API에서 응답 언어 파라미터 없음:**
- OpenAI: ❌
- Anthropic Claude: ❌
- Google Gemini/Vertex: ❌

→ **프롬프트에서 2번 이상 강조** 필요 (System + User)

---

## 구현할 클래스

### Protocol 정의
```python
class PromptTemplate(Protocol):
    def render(
        self,
        context: str,
        question: str,
        response_language: str = "Korean"
    ) -> tuple[str, str]:
        """(system_prompt, user_prompt) 반환"""
        ...
```

### 1. SimplePromptTemplate (베이스라인)
최소한의 RAG 프롬프트:

```python
class SimplePromptTemplate:
    def render(
        self,
        context: str,
        question: str,
        response_language: str = "Korean"
    ) -> tuple[str, str]:
        system = f"Answer the question based on the provided documents. Respond in {response_language}."

        user = f"""## Documents
{context}

## Question
{question}
"""
        return (system, user)
```

### 2. StrictPromptTemplate (권장)
문서 기반 답변 강제 + 할루시네이션 방지:

```python
class StrictPromptTemplate:
    # 영어 System Prompt (추론 성능 최적화)
    SYSTEM = """You are a document-based AI assistant.

## Core Principles
1. Answer based ONLY on the provided documents.
2. NEVER use prior knowledge or make assumptions.
3. If information is not found, say: "해당 정보를 제공된 문서에서 찾을 수 없습니다."
4. Always cite sources using the document numbers or names provided (e.g., [1] or [문서명]).

## Prohibited
- Supplementing answers with general knowledge
- Presenting unverified information as fact
- Omitting source citations

## Response Language (CRITICAL)
You MUST respond in {response_language}. This is mandatory.
"""

    USER = """## 참고 문서
{context}

## 질문
{question}

위 문서를 기반으로 답변하세요. 각 정보의 출처를 문서 번호나 이름으로 명시하세요.
문서에서 답을 찾을 수 없으면 솔직히 말씀해주세요.
"""

    def render(
        self,
        context: str,
        question: str,
        response_language: str = "Korean"
    ) -> tuple[str, str]:
        system = self.SYSTEM.format(response_language=response_language)
        user = self.USER.format(context=context, question=question)
        return (system, user)
```

---

## 설계 결정

### 왜 영어 System Prompt + 한국어 User Prompt?

| 구성 요소 | 언어 | 이유 |
|----------|------|------|
| System Prompt | 영어 | LLM 지시 이해력 최적화 (학습 데이터 92% 영어) |
| Context | 원본 | 번역 시 정보 손실 방지 |
| User Prompt | 한국어 | 자연스러운 UX, 응답 언어 유도 |
| 응답 언어 지시 | 양쪽에 명시 | API 파라미터 없으므로 이중 강조 |

### 언어 설정 위치
```
앱 언어 설정
     │
     └──► PromptTemplate.render(response_language="Korean")
                │
                ├──► System Prompt: "Respond in {response_language}"
                │
                └──► User Prompt: (한국어로 작성)
```

**ContextBuilder, QueryBuilder 등 다른 컴포넌트는 언어 설정 불필요**
(원본 데이터 포맷팅만 담당)

### 응답 언어 제어 팁
LLM이 영어로 응답하는 문제 해결:
1. System Prompt 마지막에 강조: `"You MUST respond in {language}"`
2. User Prompt 끝에도 추가: `"{language}로 답변하세요"`
3. Few-shot 예시 제공 (필요시)

---

## 기존 프로젝트와 차이점

기존 프로젝트 프롬프트에는:
- 클릭 가능한 링크 생성 (navigate://)
- 참고문서 섹션 형식
- 다국어 지원 명시

우리는 **단순화 + 연구 기반 개선**:
- 링크 기능 제외 (CLI 환경)
- 출처 명시 형식 표준화: `[문서명]`
- 영어 System Prompt로 추론 성능 최적화
- 명시적 응답 언어 제어

---

## 테스트 방법

1. 동일한 context + question으로 두 템플릿 비교
2. LLM 응답 품질 평가:
   - 출처 명시 여부
   - 추측성 답변 여부 (할루시네이션)
   - 답변 정확도
   - **응답 언어 일관성**
3. 다국어 테스트:
   - `response_language="Korean"` → 한국어 응답 확인
   - `response_language="English"` → 영어 응답 확인

---

## 파일
- `src/rag/prompt_template.py`
- `tests/test_prompt_template.py`

---

## 할 일
- [x] Protocol 정의 (response_language 파라미터 포함)
- [x] SimplePromptTemplate 구현
- [x] StrictPromptTemplate 구현
- [x] 응답 언어 제어 테스트
- [ ] 실제 LLM 호출로 응답 품질 비교

---

## 변경 사항

### 구현 시 조정된 부분

**출처 인용 형식 (ContextBuilder 연동)**

계획에서는 `[문서명]` 또는 `[문서명, p.N]` 형식을 직접 지정했으나,
ContextBuilder가 이미 `[번호] (파일명, p.페이지)` 형식으로 출력하므로
해당 형식을 그대로 인용하도록 변경:

```python
# 변경 전
"Always cite sources in [문서명] or [문서명, p.N] format."

# 변경 후
"Always cite sources using the document numbers or names provided (e.g., [1] or [문서명])."
```

User Prompt도 동일하게 조정:
```python
# 변경 전
"각 정보의 출처를 [문서명] 형식으로 명시하세요."

# 변경 후
"각 정보의 출처를 문서 번호나 이름으로 명시하세요."
```

### 테스트 결과
- 38개 테스트 전체 통과
- 다국어 지원 테스트 (Korean, English, Japanese, Chinese, Spanish)

---

## 참고 자료

### 프롬프트 엔지니어링
- [LangChain RAG Documentation](https://docs.langchain.com/oss/python/langchain/rag)
- [LlamaIndex Prompt Engineering](https://docs.llamaindex.ai/en/v0.10.20/examples/prompts/prompts_rag.html)
- [Prompt Engineering Guide - RAG](https://www.promptingguide.ai/research/rag)

### 할루시네이션 방지
- [Hallucination Mitigation Research (MDPI, 2025)](https://www.mdpi.com/2227-7390/13/5/856)
- [Reducing AI Hallucinations Guardrails](https://swiftflutter.com/reducing-ai-hallucinations-12-guardrails-that-cut-risk-immediately)

### 다국어 프롬프트
- [Multilingual Prompt Engineering Survey (arXiv, 2025)](https://arxiv.org/html/2505.11665v1)
- [Native vs Non-Native Language Prompting](https://arxiv.org/html/2409.07054v1)
- [Why Prompts Should Match Content Language](https://ryanstenhouse.dev/why-your-llm-prompts-should-match-your-content-language/)
- [Beyond English: Prompt Translation Strategies](https://arxiv.org/html/2502.09331v1)

### LLM API
- [OpenAI - API Language Usage](https://help.openai.com/en/articles/6742369-how-do-i-use-the-openai-api-in-different-languages)
- [Vertex AI Prompting Strategies](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/prompts/prompt-design-strategies)
- [Gemini 3 Prompting Guide](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/gemini-3-prompting-guide)

---

## Agent 전환 시 고려사항

### 개요
Strands Agent 같은 에이전트 프레임워크를 사용하면 프롬프트 템플릿의 역할이 변경됨.

### 구조 변화

| 기존 RAG | Agent 방식 |
|----------|-----------|
| 매 요청마다 템플릿으로 프롬프트 조립 | Agent 생성 시 `system_prompt` 한 번 설정 |
| `{context}` 플레이스홀더에 검색 결과 삽입 | Tool이 검색 결과 반환 |
| PromptTemplate 클래스 사용 | Tool의 docstring + system_prompt |

### 코드 비교

```python
# 기존 RAG 방식
template = StrictPromptTemplate()
system, user = template.render(context=검색결과, question=질문)
response = llm.invoke(system, user)

# Agent 방식
agent = Agent(
    system_prompt="""You are a document-based AI assistant.
    Answer based ONLY on tool results.
    Always cite sources.
    Respond in Korean.""",
    tools=[search_knowledge_base]
)
response = agent("연차 규정 알려줘")  # 끝
```

### 프롬프트 템플릿 → Agent 이전

| 기존 템플릿 요소 | Agent에서의 위치 |
|-----------------|-----------------|
| System Prompt 전체 | `Agent(system_prompt=...)` |
| `{context}` 플레이스홀더 | 제거 (Tool이 반환) |
| `{question}` 플레이스홀더 | 제거 (사용자 입력이 직접 전달) |
| `{response_language}` | system_prompt에 직접 명시 |

### Tool Docstring의 중요성

**Agent는 docstring을 보고 Tool 사용 여부를 판단함.** Strands에서는 docstring이 자동으로 tool description으로 변환됨.

```python
# ❌ 나쁜 예: Agent가 언제 써야 할지 모름
@tool
def search(q: str) -> str:
    """검색합니다."""
    pass

# ✅ 좋은 예: Agent가 정확히 판단 가능
@tool
def search_knowledge_base(query: str) -> str:
    """
    회사 내부 문서를 검색합니다.

    정책, 규정, 휴가, 복리후생 관련 질문에 사용하세요.
    실시간 재고나 주문 정보는 이 도구로 검색할 수 없습니다.

    Args:
        query: 검색할 키워드 (예: "연차 사용 방법", "재택근무 규정")

    Returns:
        검색된 문서 목록 (번호, 제목, 내용 포함)
    """
    results = vector_search(query)
    return format_results(results)
```

Strands는 docstring에서 자동 추출:
- 첫 번째 문단 → tool description
- Args 섹션 → parameter descriptions
- Type hints → parameter types

### Tool 반환값

**반환값에는 순수 데이터만 포함.** 메타데이터나 지시사항은 불필요.

```python
# ✅ 좋은 예: 결과만 반환
return "\n---\n".join([
    f"[{i}] {r['title']}\n{r['content']}"
    for i, r in enumerate(results, 1)
])

# ❌ 불필요: 메타데이터 포함
return {
    "description": "검색 결과입니다",
    "instructions": "아래 문서를 기반으로 답변하세요",
    "results": results
}
```

### 결론

Agent 도입 시:
1. **PromptTemplate 클래스** → `Agent(system_prompt=...)` 로 이전
2. **ContextBuilder** → Tool 내부 로직으로 이동 (여전히 필요)
3. **Tool docstring** → LLM이 tool 선택에 사용하므로 상세히 작성 필수
4. **Tool 반환값** → 순수 검색 결과만, 지시사항/메타데이터 불필요
