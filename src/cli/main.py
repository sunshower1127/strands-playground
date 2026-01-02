"""CLI 메인 진입점

대화형 REPL 루프를 실행합니다.
"""

import argparse
import signal
import sys
from typing import NoReturn

from .commands import CommandHandler, CommandResult
from .display import Display
from .session import CLISessionManager
from src.agent import UnifiedAgent
from src.agent.tools.search import clear_sources


def parse_args() -> argparse.Namespace:
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="Strands Agent 대화형 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project-id",
        type=int,
        default=334,
        help="프로젝트 ID (기본: 334)",
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "agent"],
        default="agent",
        help="시작 모드 (기본: agent)",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="세션 종료 시 대화 히스토리 유지",
    )
    return parser.parse_args()


class REPL:
    """대화형 REPL"""

    def __init__(
        self,
        project_id: int = 334,
        mode: str = "agent",
        persist: bool = False,
    ):
        self.display = Display()
        self.session_mgr = CLISessionManager(persist=persist)
        self.command_handler = CommandHandler()

        # 세션 및 Agent 초기화
        session = self.session_mgr.create_session()
        self.agent = UnifiedAgent(
            session_manager=session,
            project_id=project_id,
        )
        self.agent.set_mode(mode)

        # Ctrl+C 핸들링
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """시그널 핸들러 설정"""

        def handle_interrupt(signum, frame):
            self.display.info("\n\n중단됨. /exit로 종료하세요.")

        signal.signal(signal.SIGINT, handle_interrupt)

    def run(self) -> NoReturn:
        """REPL 메인 루프"""
        self.display.welcome()
        self.display.info(f"세션 ID: {self.session_mgr.session_id}")
        self.display.info(f"모드: {self.agent.current_mode}")
        self.display.info("도움말: /help")
        self.display.separator()

        try:
            while True:
                # 1. 입력 받기
                try:
                    user_input = input(self.display.prompt()).strip()
                except EOFError:
                    break

                if not user_input:
                    continue

                # 2. 명령어 체크
                if user_input.startswith("/"):
                    result = self.command_handler.handle(user_input, self)
                    if result == CommandResult.EXIT:
                        break
                    continue

                # 3. Agent 호출
                self._process_query(user_input)

        finally:
            self._cleanup()

    def _process_query(self, question: str) -> None:
        """질문 처리 (interrupt 루프 포함)"""
        # 검색 소스 초기화
        clear_sources()

        self.display.thinking()

        try:
            result = self.agent.query(question)

            # Interrupt 처리 루프
            while result.stop_reason == "interrupt":
                result = self._handle_interrupts(result)

            # 스트리밍으로 이미 출력되었으므로 구분선만 출력
            print()  # 스트리밍 출력 후 줄바꿈
            self.display.separator()

        except Exception as e:
            self.display.error(f"오류 발생: {e}")

    def _handle_interrupts(self, result):
        """Interrupt 처리"""
        responses = []

        for interrupt in result.interrupts:
            if interrupt.name == "ask_user":
                # LLM의 명확화 질문
                question = interrupt.reason.get("question", "추가 정보가 필요합니다")
                self.display.interrupt_question(question)

                try:
                    user_response = input(self.display.interrupt_prompt()).strip()
                except EOFError:
                    user_response = ""

                responses.append(
                    {
                        "interruptResponse": {
                            "interruptId": interrupt.id,
                            "response": user_response,
                        }
                    }
                )
            else:
                # 기타 interrupt
                self.display.warning(f"Interrupt: {interrupt.name}")
                reason = interrupt.reason or {}
                self.display.info(reason.get("message", ""))

                try:
                    user_response = input(self.display.interrupt_prompt()).strip()
                except EOFError:
                    user_response = ""

                responses.append(
                    {
                        "interruptResponse": {
                            "interruptId": interrupt.id,
                            "response": user_response,
                        }
                    }
                )

        return self.agent.resume(responses)

    def _extract_answer(self, result) -> str:
        """AgentResult에서 답변 텍스트 추출"""
        if not result.message:
            return "(답변 없음)"

        content_blocks = result.message.get("content", [])
        answer = ""
        for block in content_blocks:
            if isinstance(block, dict) and "text" in block:
                answer += block["text"]
        return answer or "(답변 없음)"

    def _cleanup(self) -> None:
        """종료 시 정리"""
        self.display.info("세션 정리 중...")
        self.session_mgr.cleanup()
        self.display.info("안녕히 가세요!")


def main() -> None:
    """CLI 진입점"""
    args = parse_args()

    repl = REPL(
        project_id=args.project_id,
        mode=args.mode,
        persist=args.persist,
    )
    repl.run()


if __name__ == "__main__":
    main()
