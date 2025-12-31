"""Vertex AI Claude LLM 클라이언트"""

import os
from dataclasses import dataclass
from pathlib import Path

from anthropic import AnthropicVertex
from dotenv import load_dotenv

load_dotenv()

# GCP 서비스 계정 인증 설정
_credentials_path = Path(__file__).parent.parent / "credentials" / "gcp-service-account.json"
if _credentials_path.exists() and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_credentials_path)


@dataclass
class LLMResponse:
    """LLM 응답 결과"""

    content: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMClient:
    """Vertex AI Claude 클라이언트"""

    def __init__(
        self,
        model: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
    ):
        self.model = model or os.getenv("VERTEX_CLAUDE_MODEL", "claude-sonnet-4-5@20250929")
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.region = region or os.getenv("GCP_REGION", "global")

        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID 환경변수가 필요합니다")

        self.client = AnthropicVertex(
            project_id=self.project_id,
            region=self.region,
        )

    def call(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """LLM 호출"""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)

        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
        )
