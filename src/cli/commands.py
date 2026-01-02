"""CLI 명령어 처리

/help, /exit, /clear, /mode 등 특수 명령어를 처리합니다.
"""

import os
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main import REPL


class CommandResult(Enum):
    """명령어 처리 결과"""

    CONTINUE = auto()  # REPL 계속
    EXIT = auto()  # REPL 종료


class CommandHandler:
    """명령어 핸들러"""

    def __init__(self):
        self._commands = {
            "/help": self._cmd_help,
            "/exit": self._cmd_exit,
            "/quit": self._cmd_exit,
            "/q": self._cmd_exit,
            "/clear": self._cmd_clear,
            "/mode": self._cmd_mode,
            "/status": self._cmd_status,
        }

    def handle(self, input_str: str, repl: "REPL") -> CommandResult:
        """명령어 처리"""
        parts = input_str.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in self._commands:
            return self._commands[command](repl, args)
        else:
            repl.display.warning(f"알 수 없는 명령어: {command}")
            repl.display.info("/help로 도움말을 확인하세요")
            return CommandResult.CONTINUE

    def _cmd_help(self, repl: "REPL", args: str) -> CommandResult:
        """도움말 표시"""
        help_text = """
사용 가능한 명령어:
  /help          이 도움말 표시
  /exit, /quit   CLI 종료
  /clear         화면 지우기
  /mode [모드]   모드 전환 또는 확인 (normal/agent)
  /status        현재 상태 표시

대화:
  일반 텍스트를 입력하면 Agent가 응답합니다.
  Agent가 추가 정보를 요청하면 답변해주세요.

단축키:
  Ctrl+C         현재 작업 중단
  Ctrl+D         CLI 종료
"""
        repl.display.info(help_text)
        return CommandResult.CONTINUE

    def _cmd_exit(self, repl: "REPL", args: str) -> CommandResult:
        """종료"""
        return CommandResult.EXIT

    def _cmd_clear(self, repl: "REPL", args: str) -> CommandResult:
        """화면 지우기"""
        os.system("cls" if os.name == "nt" else "clear")
        repl.display.welcome()
        return CommandResult.CONTINUE

    def _cmd_mode(self, repl: "REPL", args: str) -> CommandResult:
        """모드 전환/확인"""
        if not args:
            repl.display.info(f"현재 모드: {repl.agent.current_mode}")
            return CommandResult.CONTINUE

        mode = args.strip().lower()
        if mode in ["normal", "agent"]:
            repl.agent.set_mode(mode)
            repl.display.success(f"모드 변경: {mode}")
        else:
            repl.display.warning(f"알 수 없는 모드: {mode}")
            repl.display.info("사용 가능: normal, agent")

        return CommandResult.CONTINUE

    def _cmd_status(self, repl: "REPL", args: str) -> CommandResult:
        """상태 표시"""
        info = repl.session_mgr.get_session_info()
        repl.display.info(f"세션 ID: {info['session_id']}")
        repl.display.info(f"모드: {repl.agent.current_mode}")
        repl.display.info(f"세션 유지: {'예' if info['persist'] else '아니오'}")
        return CommandResult.CONTINUE
