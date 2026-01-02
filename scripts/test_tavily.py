"""Tavily 웹 검색 테스트 스크립트

Usage:
    python scripts/test_tavily.py
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()


def test_tavily_direct():
    """Tavily API 직접 호출 테스트"""
    print("=" * 50)
    print("1. Tavily API 직접 테스트")
    print("=" * 50)

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("❌ TAVILY_API_KEY가 설정되지 않았습니다.")
        return False

    print(f"✅ API 키 확인: {api_key[:10]}...")

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        result = client.search("한국 근로기준법 연차휴가 규정", max_results=3)

        print(f"✅ 검색 성공! 결과 {len(result.get('results', []))}개")
        for i, r in enumerate(result.get("results", []), 1):
            print(f"  [{i}] {r.get('title', 'N/A')[:50]}...")
            print(f"      URL: {r.get('url', 'N/A')[:60]}...")
        return True

    except Exception as e:
        print(f"❌ 에러: {e}")
        return False


def test_strands_tool():
    """Strands tavily_search 도구 테스트"""
    print("\n" + "=" * 50)
    print("2. Strands tavily_search 도구 테스트")
    print("=" * 50)

    try:
        from strands_tools.tavily import tavily_search

        print("✅ tavily_search import 성공")

        # 도구 정보 출력
        if hasattr(tavily_search, "__doc__"):
            print(f"   Docstring: {tavily_search.__doc__[:100] if tavily_search.__doc__ else 'N/A'}...")

        return True

    except ImportError as e:
        print(f"❌ Import 에러: {e}")
        print("   → pip install 'strands-agents-tools[tavily]' 실행 필요")
        return False
    except Exception as e:
        print(f"❌ 에러: {e}")
        return False


def test_agent_integration():
    """Agent 통합 테스트"""
    print("\n" + "=" * 50)
    print("3. Agent 통합 테스트 (웹 검색만)")
    print("=" * 50)

    try:
        from src.agent import AgentRAG

        agent = AgentRAG(project_id=334)
        print("✅ AgentRAG 초기화 성공")
        print(f"   모델: {agent.model_id}")

        # 웹 검색이 필요한 간단한 질문
        question = "2024년 한국 IT 트렌드는 무엇인가?"
        print(f"\n   질문: {question}")
        print("   (Agent 호출 중... 시간이 걸릴 수 있습니다)")

        result = agent.query(question)

        print(f"\n✅ Agent 응답 완료!")
        print(f"   답변 길이: {len(result.answer)}자")
        print(f"   도구 호출: {result.tool_calls}")
        print(f"   토큰: 입력={result.input_tokens}, 출력={result.output_tokens}")
        print(f"   소요시간: {result.latency_ms:.0f}ms")
        print(f"\n   답변 미리보기:\n   {result.answer[:300]}...")

        return True

    except Exception as e:
        print(f"❌ 에러: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🔍 Tavily 웹 검색 테스트 시작\n")

    results = []

    # 1. Tavily 직접 테스트
    results.append(("Tavily API", test_tavily_direct()))

    # 2. Strands 도구 테스트
    results.append(("Strands Tool", test_strands_tool()))

    # 3. Agent 통합 테스트 (자동 실행)
    results.append(("Agent Integration", test_agent_integration()))

    # 결과 요약
    print("\n" + "=" * 50)
    print("테스트 결과 요약")
    print("=" * 50)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
