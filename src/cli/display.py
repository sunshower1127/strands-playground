"""CLI 출력 포맷팅

색상, 스피너, 프롬프트 등 터미널 출력을 담당합니다.
"""

import sys
from typing import TextIO


class Colors:
    """ANSI 색상 코드"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


class Display:
    """터미널 출력 관리"""

    def __init__(self, stream: TextIO = sys.stdout, use_color: bool = True):
        self.stream = stream
        self.use_color = use_color and stream.isatty()

    def _colorize(self, text: str, color: str) -> str:
        """텍스트에 색상 적용"""
        if not self.use_color:
            return text
        return f"{color}{text}{Colors.RESET}"

    def welcome(self) -> None:
        """환영 메시지"""
        banner = """
========================================
   Strands Agent RAG CLI
========================================
"""
        print(self._colorize(banner, Colors.CYAN))

    def prompt(self) -> str:
        """입력 프롬프트"""
        if self.use_color:
            return f"{Colors.GREEN}{Colors.BOLD}You > {Colors.RESET}"
        return "You > "

    def interrupt_prompt(self) -> str:
        """Interrupt 응답 프롬프트"""
        if self.use_color:
            return f"{Colors.YELLOW}  >> {Colors.RESET}"
        return "  >> "

    def thinking(self) -> None:
        """생각 중 표시"""
        print(self._colorize("...", Colors.DIM))

    def answer(self, text: str) -> None:
        """답변 출력"""
        prefix = self._colorize("Agent: ", Colors.BLUE + Colors.BOLD)
        print(f"\n{prefix}{text}\n")

    def info(self, text: str) -> None:
        """정보 메시지"""
        print(self._colorize(text, Colors.DIM))

    def success(self, text: str) -> None:
        """성공 메시지"""
        print(self._colorize(f"[OK] {text}", Colors.GREEN))

    def warning(self, text: str) -> None:
        """경고 메시지"""
        print(self._colorize(f"[!] {text}", Colors.YELLOW))

    def error(self, text: str) -> None:
        """오류 메시지"""
        print(self._colorize(f"[ERROR] {text}", Colors.RED))

    def interrupt_question(self, question: str) -> None:
        """Interrupt 질문 표시"""
        prefix = self._colorize("Agent: ", Colors.MAGENTA + Colors.BOLD)
        print(f"\n{prefix}{question}")

    def separator(self) -> None:
        """구분선"""
        print(self._colorize("-" * 40, Colors.DIM))
