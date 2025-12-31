"""AWS Bedrock Titan 임베딩 클라이언트"""

import json
import os

import boto3
from dotenv import load_dotenv

load_dotenv()


class EmbeddingClient:
    """Bedrock Titan Embeddings V2 클라이언트"""

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region: str | None = None,
    ):
        self.model_id = model_id
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=self.region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

    def embed(self, text: str) -> list[float]:
        """단일 텍스트 임베딩"""
        response = self.client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": text}),
        )

        result = json.loads(response["body"].read())
        return result["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """배치 임베딩 (순차 처리)"""
        return [self.embed(text) for text in texts]
