"""QueryEnhancer 실제 연동 테스트"""

import time

from src.gemini_client import GeminiClient
from src.rag.query_enhancer import LLMQueryEnhancer, NoopQueryEnhancer


def test_noop_enhancer():
    """NoopQueryEnhancer 테스트"""
    print("\n" + "=" * 50)
    print("🔧 NoopQueryEnhancer 테스트")
    print("=" * 50)

    enhancer = NoopQueryEnhancer()

    query = "그건 어떻게 작동해?"
    history = [
        {"role": "user", "content": "Gemini API 사용법 알려줘"},
        {"role": "assistant", "content": "Gemini API는 Google의 생성형 AI API입니다."},
    ]

    result = enhancer.enhance(query, history=history)

    print(f"📝 원본 쿼리: {query}")
    print(f"📤 결과: {result}")
    print(f"✅ 예상대로 원본 반환: {result == query}")


def test_llm_enhancer():
    """LLMQueryEnhancer + GeminiClient 실제 연동 테스트"""
    print("\n" + "=" * 50)
    print("🤖 LLMQueryEnhancer + Gemini Flash 테스트")
    print("=" * 50)

    # Gemini 클라이언트 초기화
    gemini = GeminiClient()
    print(f"📡 모델: {gemini.model_name}")
    print(f"🌍 리전: {gemini.location}")

    enhancer = LLMQueryEnhancer(llm_client=gemini)

    # 테스트 케이스들
    test_cases = [
        {
            "name": "대명사 해소",
            "query": "그건 어떻게 작동해?",
            "history": [
                {"role": "user", "content": "Gemini API 사용법 알려줘"},
                {"role": "assistant", "content": "Gemini API는 Google의 생성형 AI API입니다. REST API를 통해 호출할 수 있습니다."},
            ],
        },
        {
            "name": "맥락 참조",
            "query": "더 자세히 알려줘",
            "history": [
                {"role": "user", "content": "연차 휴가 정책이 뭐야?"},
                {"role": "assistant", "content": "연차 휴가는 1년에 15일이 기본 제공됩니다."},
            ],
        },
        {
            "name": "독립 질문 (원본 유지 기대)",
            "query": "오늘 날씨 어때?",
            "history": [
                {"role": "user", "content": "Gemini API 사용법 알려줘"},
                {"role": "assistant", "content": "Gemini API는 Google의 생성형 AI API입니다."},
            ],
        },
        {
            "name": "히스토리 없음",
            "query": "연차 휴가는 며칠이야?",
            "history": None,
        },
    ]

    for tc in test_cases:
        print(f"\n📋 테스트: {tc['name']}")
        print(f"   원본: {tc['query']}")

        start = time.time()
        result = enhancer.enhance(tc["query"], history=tc["history"])
        elapsed = (time.time() - start) * 1000

        print(f"   결과: {result}")
        print(f"   ⏱️  레이턴시: {elapsed:.0f}ms")


def main():
    """메인 테스트 실행"""
    print("\n🚀 QueryEnhancer 연동 테스트 시작")

    test_noop_enhancer()
    test_llm_enhancer()

    print("\n✅ 모든 테스트 완료!")


if __name__ == "__main__":
    main()
