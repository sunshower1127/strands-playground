"""Agent RAG 테스트 스크립트

간단한 질문으로 Agent RAG 파이프라인을 테스트합니다.

Usage:
    uv run python scripts/test_agent.py
    uv run python scripts/test_agent.py "연차 휴가는 며칠인가요?"
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.agent import AgentRAG


def main():
    # 질문 (인자로 받거나 기본값)
    question = sys.argv[1] if len(sys.argv) > 1 else "연차 휴가는 며칠인가요?"

    print("=" * 60)
    print("🤖 Agent RAG 테스트")
    print("=" * 60)
    print(f"\n질문: {question}\n")

    # Agent 생성 및 실행
    print("Agent 생성 중...")
    agent = AgentRAG(project_id=334)

    print("질문 처리 중...\n")
    result = agent.query(question)

    # 결과 출력
    print("-" * 60)
    print("📝 답변:")
    print("-" * 60)
    print(result.answer)

    print("\n" + "-" * 60)
    print("📊 통계:")
    print("-" * 60)
    print(f"  도구 호출 횟수: {result.tool_call_count}")
    print(f"  입력 토큰: {result.input_tokens}")
    print(f"  출력 토큰: {result.output_tokens}")
    print(f"  총 토큰: {result.total_tokens}")
    print(f"  레이턴시: {result.latency_ms:.1f}ms")
    print(f"  모델: {result.model}")

    if result.tool_calls:
        print("\n📋 도구 호출 상세:")
        for i, tc in enumerate(result.tool_calls, 1):
            print(f"  {i}. {tc['name']}: 호출 {tc['count']}회 (성공: {tc['success']}, 실패: {tc['error']})")


if __name__ == "__main__":
    main()
