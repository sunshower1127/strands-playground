"""CLI 세션 관리

FileSessionManager를 사용하여 세션을 파일 기반으로 관리합니다.
CLI 시작 시 세션 생성, 종료 시 삭제.
"""

import shutil
import uuid
from pathlib import Path

from strands.session.file_session_manager import FileSessionManager

# 세션 저장 디렉토리
SESSIONS_DIR = Path(__file__).parent.parent.parent / "sessions"


class CLISessionManager:
    """CLI 전용 세션 매니저

    - CLI 시작 시 고유 session_id 생성
    - FileSessionManager로 대화 히스토리 저장
    - CLI 종료 시 세션 파일 삭제 (임시 세션)
    """

    def __init__(self, storage_dir: Path = SESSIONS_DIR, persist: bool = False):
        """
        Args:
            storage_dir: 세션 저장 디렉토리
            persist: True면 종료 시 세션 유지 (나중에 복원 가능)
        """
        self.storage_dir = storage_dir
        self.persist = persist
        self.session_id: str | None = None
        self.session_manager: FileSessionManager | None = None

    def create_session(self) -> FileSessionManager:
        """새 세션 생성"""
        self.session_id = f"cli-{uuid.uuid4().hex[:8]}"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.session_manager = FileSessionManager(
            session_id=self.session_id,
            storage_dir=str(self.storage_dir),
        )

        return self.session_manager

    def cleanup(self) -> None:
        """세션 정리 (persist=False일 때만 삭제)"""
        if self.persist or not self.session_id:
            return

        # 세션 파일 삭제
        session_path = self.storage_dir / self.session_id
        if session_path.exists():
            shutil.rmtree(session_path)

    def get_session_info(self) -> dict:
        """현재 세션 정보 반환"""
        return {
            "session_id": self.session_id,
            "storage_dir": str(self.storage_dir),
            "persist": self.persist,
        }
