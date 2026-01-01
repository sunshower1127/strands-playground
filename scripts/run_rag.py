"""RAG 파이프라인 테스트 러너

질문셋을 실행하고 결과를 저장합니다.

Usage:
    # 기본 실행 (minimal pipeline)
    uv run python scripts/run_rag.py

    # 파이프라인 선택
    uv run python scripts/run_rag.py --pipeline minimal
    uv run python scripts/run_rag.py --pipeline standard
    uv run python scripts/run_rag.py --pipeline full

    # 특정 질문만 실행
    uv run python scripts/run_rag.py --questions 1,2,3

    # 레벨 필터
    uv run python scripts/run_rag.py --level 1

    # 설정만 출력
    uv run python scripts/run_rag.py --dry-run
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tqdm import tqdm

from src.rag import (
    create_full_pipeline,
    create_minimal_pipeline,
    create_standard_pipeline,
)

# =============================================================================
# 경로 설정
# =============================================================================

QUESTIONS_PATH = PROJECT_ROOT / "data" / "questions" / "question_set.json"
RESULTS_DIR = PROJECT_ROOT / "data" / "results"


# =============================================================================
# 질문셋 로드
# =============================================================================


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    """질문셋 로드"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]


def filter_questions(
    questions: list[dict],
    question_ids: list[int] | None = None,
    level: int | None = None,
) -> list[dict]:
    """질문 필터링"""
    result = questions

    if question_ids:
        result = [q for q in result if q["id"] in question_ids]

    if level:
        result = [q for q in result if q["level"] == level]

    return result


# =============================================================================
# 파이프라인 설정
# =============================================================================

PIPELINE_FACTORIES = {
    "minimal": create_minimal_pipeline,
    "standard": create_standard_pipeline,
    "full": create_full_pipeline,
}


def get_pipeline_config(pipeline_name: str) -> dict:
    """파이프라인 설정 정보 반환 (결과 저장용)"""
    configs = {
        "minimal": {
            "name": "minimal",
            "preprocessor": None,
            "query_enhancer": None,
            "query_builder": "KNNQueryBuilder",
            "result_filter": None,
            "chunk_expander": None,
            "context_builder": "SimpleContextBuilder",
            "prompt_template": "SimplePromptTemplate",
            "search_size": 5,
            "search_pipeline": None,
        },
        "standard": {
            "name": "standard",
            "preprocessor": None,
            "query_enhancer": None,
            "query_builder": "HybridQueryBuilder",
            "result_filter": "TopKFilter(k=5)",
            "chunk_expander": None,
            "context_builder": "RankedContextBuilder(reorder=True)",
            "prompt_template": "StrictPromptTemplate",
            "search_size": 20,
            "search_pipeline": "hybrid-rrf",
        },
        "full": {
            "name": "full",
            "preprocessor": "KoreanPreprocessor",
            "query_enhancer": None,
            "query_builder": "HybridQueryBuilder",
            "result_filter": "CompositeFilter([TopKFilter(k=20), RerankerFilter(top_k=5)])",
            "chunk_expander": "NeighborChunkExpander(window=5)",
            "context_builder": "RankedContextBuilder(reorder=True)",
            "prompt_template": "StrictPromptTemplate",
            "search_size": 50,
            "search_pipeline": "hybrid-rrf",
        },
    }
    return configs.get(pipeline_name, configs["minimal"])


# =============================================================================
# 결과 저장
# =============================================================================


def save_results(
    results: list[dict],
    config: dict,
    run_id: str,
    output_dir: Path = RESULTS_DIR,
) -> Path:
    """결과를 JSON 파일로 저장"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 통계 계산
    summary = calculate_summary(results)

    # 결과 파일 구성
    output = {
        "run_id": run_id,
        "config": config,
        "results": results,
        "summary": summary,
    }

    # 저장
    filename = f"{run_id}_{config['name']}.json"
    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output_path


def calculate_summary(results: list[dict]) -> dict:
    """결과 통계 계산"""
    if not results:
        return {}

    total = len(results)
    latencies = [r["latency_ms"] for r in results]
    input_tokens = sum(r["input_tokens"] for r in results)
    output_tokens = sum(r["output_tokens"] for r in results)

    # 레벨별 통계
    by_level = defaultdict(lambda: {"count": 0, "latencies": []})
    for r in results:
        level = r["level"]
        by_level[level]["count"] += 1
        by_level[level]["latencies"].append(r["latency_ms"])

    level_stats = {}
    for level, data in sorted(by_level.items()):
        level_stats[str(level)] = {
            "count": data["count"],
            "avg_latency_ms": round(sum(data["latencies"]) / len(data["latencies"]), 1),
        }

    return {
        "total_questions": total,
        "avg_latency_ms": round(sum(latencies) / total, 1),
        "min_latency_ms": round(min(latencies), 1),
        "max_latency_ms": round(max(latencies), 1),
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "by_level": level_stats,
    }


# =============================================================================
# 출력
# =============================================================================


def print_summary(results: list[dict], config: dict) -> None:
    """결과 요약 출력"""
    summary = calculate_summary(results)

    print("\n" + "=" * 60)
    print(f"📊 실행 결과 요약 ({config['name']} pipeline)")
    print("=" * 60)

    print(f"\n총 질문 수: {summary['total_questions']}")
    print(f"평균 레이턴시: {summary['avg_latency_ms']:.1f}ms")
    print(f"최소/최대: {summary['min_latency_ms']:.1f}ms / {summary['max_latency_ms']:.1f}ms")
    print(f"\n총 토큰: {summary['total_tokens']:,}")
    print(f"  - 입력: {summary['total_input_tokens']:,}")
    print(f"  - 출력: {summary['total_output_tokens']:,}")

    print("\n레벨별 통계:")
    for level, stats in summary["by_level"].items():
        print(f"  Level {level}: {stats['count']}개, 평균 {stats['avg_latency_ms']:.1f}ms")

    print("=" * 60)


def print_config(config: dict) -> None:
    """설정 출력 (dry-run용)"""
    print("\n" + "=" * 60)
    print(f"🔧 파이프라인 설정: {config['name']}")
    print("=" * 60)

    for key, value in config.items():
        if key != "name":
            print(f"  {key}: {value}")

    print("=" * 60)


# =============================================================================
# 메인
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="RAG 파이프라인 테스트 러너")
    parser.add_argument(
        "--pipeline",
        choices=["minimal", "standard", "full"],
        default="minimal",
        help="사용할 파이프라인 (기본: minimal)",
    )
    parser.add_argument(
        "--questions",
        type=str,
        help="실행할 질문 ID (쉼표 구분, 예: 1,2,3)",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=[1, 2, 3, 4],
        help="실행할 레벨 필터",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="설정만 출력하고 종료",
    )
    parser.add_argument(
        "--project-id",
        type=int,
        default=334,
        help="프로젝트 ID (기본: 334)",
    )

    args = parser.parse_args()

    # 설정 로드
    config = get_pipeline_config(args.pipeline)

    # dry-run
    if args.dry_run:
        print_config(config)
        questions = load_questions()
        question_ids = [int(x) for x in args.questions.split(",")] if args.questions else None
        filtered = filter_questions(questions, question_ids, args.level)
        print(f"\n실행 대상: {len(filtered)}개 질문")
        for q in filtered:
            print(f"  [{q['id']}] Level {q['level']}: {q['question'][:40]}...")
        return

    # 파이프라인 생성
    print(f"\n🚀 파이프라인 생성 중... ({args.pipeline})")
    factory = PIPELINE_FACTORIES[args.pipeline]
    pipeline = factory(project_id=args.project_id)

    # 질문 로드 및 필터
    questions = load_questions()
    question_ids = [int(x) for x in args.questions.split(",")] if args.questions else None
    questions = filter_questions(questions, question_ids, args.level)

    if not questions:
        print("❌ 실행할 질문이 없습니다.")
        return

    print(f"📝 {len(questions)}개 질문 실행 예정\n")

    # 실행
    results = []
    for q in tqdm(questions, desc="질문 처리"):
        try:
            result = pipeline.query(q["question"])
            results.append({
                "id": q["id"],
                "level": q["level"],
                "category": q["category"],
                "question": q["question"],
                "expected_answer": q.get("expected_answer", ""),
                "key_facts": q.get("key_facts", []),
                "documents_required": q.get("documents_required", []),
                "answer": result.answer,
                "sources": [
                    {
                        "file_name": s["_source"].get("file_name", "unknown"),
                        "score": s.get("_score", 0),
                    }
                    for s in result.sources
                ],
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "latency_ms": round(result.latency_ms, 1),
                "model": result.model,
            })
        except Exception as e:
            print(f"\n❌ 질문 {q['id']} 실패: {e}")
            results.append({
                "id": q["id"],
                "level": q["level"],
                "category": q["category"],
                "question": q["question"],
                "expected_answer": q.get("expected_answer", ""),
                "key_facts": q.get("key_facts", []),
                "documents_required": q.get("documents_required", []),
                "answer": f"ERROR: {e}",
                "sources": [],
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
                "model": "",
                "error": str(e),
            })

    # 결과 저장
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = save_results(results, config, run_id)
    print(f"\n💾 결과 저장: {output_path}")

    # 요약 출력
    print_summary(results, config)


if __name__ == "__main__":
    main()
