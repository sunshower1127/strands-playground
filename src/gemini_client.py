"""Vertex AI Gemini 클라이언트 (QueryEnhancer용 빠른 모델)"""

import os
from dataclasses import dataclass
from pathlib import Path

import vertexai
from dotenv import load_dotenv
from vertexai.generative_models import GenerativeModel

load_dotenv()

# GCP 서비스 계정 인증 설정
_credentials_path = Path(__file__).parent.parent / "credentials" / "gcp-service-account.json"
if _credentials_path.exists() and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_credentials_path)


@dataclass
class GeminiResponse:
    """Gemini 응답 결과"""

    content: str
    input_tokens: int
    output_tokens: int
    model: str


class GeminiClient:
    """Vertex AI Gemini 클라이언트 (Flash 모델용)"""

    _initialized = False

    def __init__(
        self,
        model: str | None = None,
        project_id: str | None = None,
        location: str | None = None,
    ):
        self.model_name = model or os.getenv("VERTEX_GEMINI_MODEL", "gemini-2.0-flash-001")
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.location = location or os.getenv("GCP_GEMINI_LOCATION", "us-central1")

        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID 환경변수가 필요합니다")

        # Vertex AI 초기화 (한 번만)
        if not GeminiClient._initialized:
            vertexai.init(project=self.project_id, location=self.location)
            GeminiClient._initialized = True

        self.model = GenerativeModel(self.model_name)

    def call(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 256,
    ) -> GeminiResponse:
        """Gemini 호출"""
        # 시스템 프롬프트가 있으면 프롬프트에 포함
        if system:
            full_prompt = f"{system}\n\n{prompt}"
        else:
            full_prompt = prompt

        response = self.model.generate_content(
            full_prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": 0.1,  # 일관된 출력을 위해 낮은 temperature
            },
        )

        # 토큰 사용량 추출
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0

        return GeminiResponse(
            content=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model_name,
        )
