"""LLM 비용 계산 모듈

토큰 사용량을 기반으로 비용을 추정합니다.

Usage:
    from src.cost import calculate_cost, format_cost

    cost = calculate_cost(
        input_tokens=3000,
        output_tokens=500,
        model="claude-sonnet-4-5-20250929"
    )
    print(format_cost(cost))  # "$0.0120 (₩17)"
"""

# =============================================================================
# 상수
# =============================================================================

# 환율 (USD → KRW)
USD_TO_KRW = 1450

# 모델별 가격 (USD per 1M tokens)
# https://cloud.google.com/vertex-ai/generative-ai/pricing
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Claude Sonnet 4 (Vertex AI)
    "claude-sonnet-4-5-20250929": {
        "input": 3.0,   # $3 / 1M input tokens
        "output": 15.0,  # $15 / 1M output tokens
    },
    "vertex_ai/claude-sonnet-4-5@20250929": {
        "input": 3.0,
        "output": 15.0,
    },
    # Claude Haiku 3.5 (Vertex AI)
    "claude-3-5-haiku-20241022": {
        "input": 0.80,
        "output": 4.0,
    },
    # Claude Opus 4 (Vertex AI)
    "claude-opus-4-5-20251101": {
        "input": 15.0,
        "output": 75.0,
    },
    # 기본값 (알 수 없는 모델)
    "default": {
        "input": 3.0,
        "output": 15.0,
    },
}


# =============================================================================
# 비용 계산
# =============================================================================


def get_pricing(model: str) -> dict[str, float]:
    """모델별 가격 정보 반환"""
    # 정확히 매칭
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]

    # 부분 매칭 (모델명에 키워드 포함)
    model_lower = model.lower()
    if "sonnet" in model_lower:
        return MODEL_PRICING["claude-sonnet-4-5-20250929"]
    if "haiku" in model_lower:
        return MODEL_PRICING["claude-3-5-haiku-20241022"]
    if "opus" in model_lower:
        return MODEL_PRICING["claude-opus-4-5-20251101"]

    return MODEL_PRICING["default"]


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "default",
) -> dict[str, float]:
    """토큰 사용량으로 비용 계산

    Args:
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        model: 모델명

    Returns:
        dict: {
            "input_usd": 입력 비용 (USD),
            "output_usd": 출력 비용 (USD),
            "total_usd": 총 비용 (USD),
            "total_krw": 총 비용 (KRW),
        }
    """
    pricing = get_pricing(model)

    input_usd = (input_tokens / 1_000_000) * pricing["input"]
    output_usd = (output_tokens / 1_000_000) * pricing["output"]
    total_usd = input_usd + output_usd
    total_krw = total_usd * USD_TO_KRW

    return {
        "input_usd": input_usd,
        "output_usd": output_usd,
        "total_usd": total_usd,
        "total_krw": total_krw,
    }


def format_cost(cost: dict[str, float], include_breakdown: bool = False) -> str:
    """비용을 문자열로 포맷팅

    Args:
        cost: calculate_cost() 결과
        include_breakdown: 입력/출력 비용 분리 표시 여부

    Returns:
        str: "$0.0120 (₩17)" 또는 "in: $0.01, out: $0.01, total: $0.02 (₩29)"
    """
    if include_breakdown:
        return (
            f"in: ${cost['input_usd']:.4f}, "
            f"out: ${cost['output_usd']:.4f}, "
            f"total: ${cost['total_usd']:.4f} (₩{cost['total_krw']:.0f})"
        )
    return f"${cost['total_usd']:.4f} (₩{cost['total_krw']:.0f})"


def calculate_total_cost(results: list[dict], model: str = "default") -> dict[str, float]:
    """여러 결과의 총 비용 계산

    Args:
        results: [{"input_tokens": int, "output_tokens": int}, ...]
        model: 모델명

    Returns:
        dict: calculate_cost()와 동일한 형식
    """
    total_input = sum(r.get("input_tokens", 0) for r in results)
    total_output = sum(r.get("output_tokens", 0) for r in results)
    return calculate_cost(total_input, total_output, model)
