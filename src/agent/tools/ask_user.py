"""ask_user 도구

LLM이 사용자에게 명확화 질문을 할 때 사용합니다.
호출 시 interrupt를 발생시켜 REPL 루프에서 처리합니다.
"""

from strands import tool


@tool
def ask_user(question: str, tool_context) -> str:
    """사용자에게 명확화 질문을 합니다.

    질문이 불명확하거나 추가 정보가 필요할 때 사용하세요.
    예: "국내출장과 해외출장 중 어느 것을 알고 싶으신가요?"

    Args:
        question: 사용자에게 물어볼 질문

    Returns:
        사용자의 응답 (interrupt 처리 후 반환됨)
    """
    # Interrupt 발생 - REPL에서 사용자 입력 받음
    response = tool_context.interrupt("ask_user", reason={"question": question})
    return response
