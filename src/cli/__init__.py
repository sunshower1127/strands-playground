"""CLI 모듈

대화형 REPL CLI 도구를 제공합니다.
"""

__all__ = ["main"]


def main():
    """CLI 진입점 (lazy import로 순환 참조 방지)"""
    from .main import main as _main

    _main()
