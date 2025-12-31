"""LLM 클라이언트 테스트"""

import sys

sys.path.insert(0, "src")

from llm_client import LLMClient


def main():
    print("=== LLM Client Test ===\n")

    client = LLMClient()
    print(f"Model: {client.model}")
    print(f"Project: {client.project_id}")
    print(f"Region: {client.region}")
    print()

    print("Calling LLM...")
    response = client.call("안녕하세요! 간단히 자기소개 해주세요. 2문장으로.")

    print(f"\n--- Response ---")
    print(f"Content: {response.content}")
    print(f"Input tokens: {response.input_tokens}")
    print(f"Output tokens: {response.output_tokens}")
    print(f"Model: {response.model}")


if __name__ == "__main__":
    main()
