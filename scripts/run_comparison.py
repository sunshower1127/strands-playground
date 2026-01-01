"""Basic vs Agent RAG 비교 평가 러너

두 모드로 동일한 질문셋을 실행하고 결과를 비교합니다.

Usage:
    # 전체 실행
    uv run python scripts/run_comparison.py

    # 특정 질문만
    uv run python scripts/run_comparison.py --questions 1,2,3

    # 레벨 필터
    uv run python scripts/run_comparison.py --level 1

    # 한 모드만 실행 (이미 결과가 있을 때)
    uv run python scripts/run_comparison.py --mode basic
    uv run python scripts/run_comparison.py --mode agent

    # 기존 결과로 비교만
    uv run python scripts/run_comparison.py --compare-only data/results/basic.json data/results/agent.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import create_service
from src.cost import calculate_cost, format_cost
from tqdm import tqdm


# =============================================================================
# Key Facts 자동 매칭
# =============================================================================


def check_key_facts(answer: str, key_facts: list[str]) -> dict:
    """답변에서 key_facts 포함 여부 체크

    Args:
        answer: 생성된 답변
        key_facts: 정답에 포함되어야 할 핵심 사실 리스트

    Returns:
        dict: matched(매칭된 facts), missed(누락된 facts), accuracy(정확도)
    """
    if not key_facts:
        return {"matched": [], "missed": [], "accuracy": 1.0}
    if not answer:
        return {"matched": [], "missed": key_facts, "accuracy": 0.0}

    answer_lower = answer.lower()
    matched = []
    missed = []

    for fact in key_facts:
        fact_lower = fact.lower()
        # 핵심 키워드 추출 (숫자, 한글 단어)
        keywords = re.findall(r"[\d]+|[가-힣]+", fact_lower)
        # 의미 있는 키워드만 필터 (2자 이상)
        meaningful_keywords = [kw for kw in keywords if len(kw) > 1]

        if not meaningful_keywords:
            # 키워드가 없으면 전체 문자열 포함 여부 체크
            if fact_lower in answer_lower:
                matched.append(fact)
            else:
                missed.append(fact)
        else:
            # 모든 키워드가 답변에 포함되면 매칭
            if all(kw in answer_lower for kw in meaningful_keywords):
                matched.append(fact)
            else:
                missed.append(fact)

    accuracy = len(matched) / len(key_facts)
    return {"matched": matched, "missed": missed, "accuracy": round(accuracy, 4)}


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
# 실행
# =============================================================================


def run_mode(
    mode: str,
    questions: list[dict],
    project_id: int = 334,
) -> list[dict]:
    """특정 모드로 질문셋 실행"""
    print(f"\n🚀 {mode.upper()} 모드 실행 중...")

    service = create_service(mode=mode, project_id=project_id)
    results = []

    for q in tqdm(questions, desc=f"{mode} 처리"):
        try:
            result = service.query(q["question"])
            results.append(
                {
                    "id": q["id"],
                    "level": q["level"],
                    "category": q["category"],
                    "question": q["question"],
                    "expected_answer": q.get("expected_answer", ""),
                    "key_facts": q.get("key_facts", []),
                    "documents_required": q.get("documents_required", []),
                    "answer": result.answer,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "latency_ms": round(result.latency_ms, 1),
                    "model": result.model,
                    # 모드 공통 정보
                    "sources": result.sources,
                    "timings": result.timings,
                    # Agent 모드 전용
                    "tool_calls": result.tool_calls if mode == "agent" else [],
                    "call_history": result.call_history if mode == "agent" else [],
                }
            )
        except Exception as e:
            print(f"\n❌ 질문 {q['id']} 실패: {e}")
            results.append(
                {
                    "id": q["id"],
                    "level": q["level"],
                    "category": q["category"],
                    "question": q["question"],
                    "expected_answer": q.get("expected_answer", ""),
                    "key_facts": q.get("key_facts", []),
                    "documents_required": q.get("documents_required", []),
                    "answer": f"ERROR: {e}",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "latency_ms": 0,
                    "model": "",
                    "error": str(e),
                    "sources": [],
                    "tool_calls": [],
                    "call_history": [],
                    "timings": {},
                }
            )

    return results


# =============================================================================
# 통계 계산
# =============================================================================


def calculate_summary(results: list[dict]) -> dict:
    """결과 통계 계산"""
    if not results:
        return {}

    total = len(results)
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
    input_tokens = sum(r["input_tokens"] for r in results)
    output_tokens = sum(r["output_tokens"] for r in results)

    # 레벨별 통계
    by_level = defaultdict(lambda: {"count": 0, "latencies": []})
    for r in results:
        level = r["level"]
        by_level[level]["count"] += 1
        if r["latency_ms"] > 0:
            by_level[level]["latencies"].append(r["latency_ms"])

    level_stats = {}
    for level, data in sorted(by_level.items()):
        avg_latency = sum(data["latencies"]) / len(data["latencies"]) if data["latencies"] else 0
        level_stats[str(level)] = {
            "count": data["count"],
            "avg_latency_ms": round(avg_latency, 1),
        }

    return {
        "total_questions": total,
        "success_count": len(latencies),
        "error_count": total - len(latencies),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "min_latency_ms": round(min(latencies), 1) if latencies else 0,
        "max_latency_ms": round(max(latencies), 1) if latencies else 0,
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "by_level": level_stats,
    }


# =============================================================================
# 비교 및 병합
# =============================================================================


def merge_results(basic_results: list[dict], agent_results: list[dict]) -> list[dict]:
    """Basic과 Agent 결과 병합"""
    # ID로 인덱싱
    agent_by_id = {r["id"]: r for r in agent_results}

    merged = []
    for b in basic_results:
        q_id = b["id"]
        a = agent_by_id.get(q_id, {})
        key_facts = b.get("key_facts", [])

        # Key Facts 자동 매칭
        basic_check = check_key_facts(b["answer"], key_facts)
        agent_check = check_key_facts(a.get("answer", ""), key_facts)

        merged.append(
            {
                "id": q_id,
                "level": b["level"],
                "category": b["category"],
                "question": b["question"],
                "expected_answer": b.get("expected_answer", ""),
                "key_facts": key_facts,
                # Basic 결과
                "answer_basic": b["answer"],
                "latency_basic_ms": b["latency_ms"],
                "tokens_basic": {
                    "input": b["input_tokens"],
                    "output": b["output_tokens"],
                    "total": b["input_tokens"] + b["output_tokens"],
                },
                "sources_basic": b.get("sources", []),
                "timings_basic": b.get("timings", {}),
                # Basic Key Facts 매칭
                "key_facts_matched_basic": basic_check["matched"],
                "key_facts_missed_basic": basic_check["missed"],
                "accuracy_basic": basic_check["accuracy"],
                # Agent 결과
                "answer_agent": a.get("answer", "N/A"),
                "latency_agent_ms": a.get("latency_ms", 0),
                "tokens_agent": {
                    "input": a.get("input_tokens", 0),
                    "output": a.get("output_tokens", 0),
                    "total": a.get("input_tokens", 0) + a.get("output_tokens", 0),
                },
                "sources_agent": a.get("sources", []),
                "timings_agent": a.get("timings", {}),
                "tool_calls": a.get("tool_calls", []),
                "call_history": a.get("call_history", []),
                # Agent Key Facts 매칭
                "key_facts_matched_agent": agent_check["matched"],
                "key_facts_missed_agent": agent_check["missed"],
                "accuracy_agent": agent_check["accuracy"],
                # 평가 (수동 입력용)
                "winner": "",
                "notes": "",
            }
        )

    return merged


def calculate_comparison_stats(merged: list[dict]) -> dict:
    """비교 통계 계산"""
    basic_latencies = [m["latency_basic_ms"] for m in merged if m["latency_basic_ms"] > 0]
    agent_latencies = [m["latency_agent_ms"] for m in merged if m["latency_agent_ms"] > 0]

    # 토큰 계산 (이제 객체 형태)
    basic_input = sum(m["tokens_basic"]["input"] for m in merged)
    basic_output = sum(m["tokens_basic"]["output"] for m in merged)
    basic_tokens = basic_input + basic_output

    agent_input = sum(m["tokens_agent"]["input"] for m in merged)
    agent_output = sum(m["tokens_agent"]["output"] for m in merged)
    agent_tokens = agent_input + agent_output

    # 비용 계산 (정확한 input/output 값 사용)
    basic_cost = calculate_cost(basic_input, basic_output)
    agent_cost = calculate_cost(agent_input, agent_output)

    # 정확도 통계
    basic_accuracies = [m["accuracy_basic"] for m in merged if m.get("key_facts")]
    agent_accuracies = [m["accuracy_agent"] for m in merged if m.get("key_facts")]

    # 효율성 지표 계산
    basic_matched_facts = sum(len(m.get("key_facts_matched_basic", [])) for m in merged)
    agent_matched_facts = sum(len(m.get("key_facts_matched_agent", [])) for m in merged)
    total_latency_basic = sum(basic_latencies)
    total_latency_agent = sum(agent_latencies)

    efficiency = {}
    if basic_matched_facts > 0:
        efficiency["basic"] = {
            "tokens_per_fact": round(basic_tokens / basic_matched_facts, 1),
            "latency_per_fact_ms": round(total_latency_basic / basic_matched_facts, 1),
            "cost_per_fact_krw": round(basic_cost["total_krw"] / basic_matched_facts, 2),
        }
    if agent_matched_facts > 0:
        efficiency["agent"] = {
            "tokens_per_fact": round(agent_tokens / agent_matched_facts, 1),
            "latency_per_fact_ms": round(total_latency_agent / agent_matched_facts, 1),
            "cost_per_fact_krw": round(agent_cost["total_krw"] / agent_matched_facts, 2),
        }

    # 레벨별 비교
    by_level = defaultdict(
        lambda: {
            "count": 0,
            "basic_latencies": [],
            "agent_latencies": [],
        }
    )
    for m in merged:
        level = m["level"]
        by_level[level]["count"] += 1
        if m["latency_basic_ms"] > 0:
            by_level[level]["basic_latencies"].append(m["latency_basic_ms"])
        if m["latency_agent_ms"] > 0:
            by_level[level]["agent_latencies"].append(m["latency_agent_ms"])

    level_stats = {}
    for level, data in sorted(by_level.items()):
        basic_avg = sum(data["basic_latencies"]) / len(data["basic_latencies"]) if data["basic_latencies"] else 0
        agent_avg = sum(data["agent_latencies"]) / len(data["agent_latencies"]) if data["agent_latencies"] else 0
        level_stats[str(level)] = {
            "count": data["count"],
            "basic_avg_latency_ms": round(basic_avg, 1),
            "agent_avg_latency_ms": round(agent_avg, 1),
            "latency_diff_ms": round(agent_avg - basic_avg, 1),
        }

    return {
        "total_questions": len(merged),
        "basic": {
            "avg_latency_ms": round(sum(basic_latencies) / len(basic_latencies), 1) if basic_latencies else 0,
            "tokens": {
                "input": basic_input,
                "output": basic_output,
                "total": basic_tokens,
            },
            "cost_usd": round(basic_cost["total_usd"], 4),
            "cost_krw": round(basic_cost["total_krw"], 0),
        },
        "agent": {
            "avg_latency_ms": round(sum(agent_latencies) / len(agent_latencies), 1) if agent_latencies else 0,
            "tokens": {
                "input": agent_input,
                "output": agent_output,
                "total": agent_tokens,
            },
            "cost_usd": round(agent_cost["total_usd"], 4),
            "cost_krw": round(agent_cost["total_krw"], 0),
        },
        "latency_diff_ms": round(
            (sum(agent_latencies) / len(agent_latencies) if agent_latencies else 0)
            - (sum(basic_latencies) / len(basic_latencies) if basic_latencies else 0),
            1,
        ),
        "token_diff": {
            "input": agent_input - basic_input,
            "output": agent_output - basic_output,
            "total": agent_tokens - basic_tokens,
        },
        "cost_diff_usd": round(agent_cost["total_usd"] - basic_cost["total_usd"], 4),
        "cost_diff_krw": round(agent_cost["total_krw"] - basic_cost["total_krw"], 0),
        "accuracy": {
            "basic_avg": round(sum(basic_accuracies) / len(basic_accuracies), 4) if basic_accuracies else 0,
            "agent_avg": round(sum(agent_accuracies) / len(agent_accuracies), 4) if agent_accuracies else 0,
            "basic_perfect": sum(1 for a in basic_accuracies if a == 1.0),
            "agent_perfect": sum(1 for a in agent_accuracies if a == 1.0),
        },
        "efficiency": efficiency,
        "matched_facts": {
            "basic": basic_matched_facts,
            "agent": agent_matched_facts,
        },
        "by_level": level_stats,
    }


# =============================================================================
# 저장
# =============================================================================


def save_results(
    results: list[dict],
    mode: str,
    run_id: str,
    output_dir: Path = RESULTS_DIR,
) -> Path:
    """단일 모드 결과 저장"""
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = calculate_summary(results)

    output = {
        "run_id": run_id,
        "mode": mode,
        "results": results,
        "summary": summary,
    }

    filename = f"{run_id}_{mode}.json"
    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output_path


def save_comparison(
    merged: list[dict],
    run_id: str,
    output_dir: Path = RESULTS_DIR,
) -> Path:
    """비교 결과 저장"""
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = calculate_comparison_stats(merged)

    output = {
        "run_id": run_id,
        "type": "comparison",
        "results": merged,
        "stats": stats,
    }

    filename = f"{run_id}_comparison.json"
    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output_path


def save_agent_call_log(
    merged: list[dict],
    run_id: str,
    output_dir: Path = RESULTS_DIR,
) -> Path:
    """Agent 도구 호출 로그 파일 생성

    각 질문별로 Agent가 어떤 순서로 도구를 호출했는지,
    어떤 검색 쿼리를 사용했고 어떤 문서를 찾았는지 기록합니다.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("=" * 80)
    lines.append(f"Agent RAG 도구 호출 로그 - {run_id}")
    lines.append("=" * 80)
    lines.append("")

    for m in merged:
        q_id = m["id"]
        question = m["question"]
        call_history = m.get("call_history", [])

        lines.append("-" * 80)
        lines.append(f"Q{q_id}: {question}")
        lines.append("-" * 80)

        if not call_history:
            lines.append("  (도구 호출 없음)")
        else:
            for call in call_history:
                call_idx = call.get("call_index", "?")
                tool = call.get("tool", "unknown")
                query = call.get("query", "")
                elapsed = call.get("elapsed_ms", 0)
                result_count = call.get("result_count", 0)

                lines.append(f"  [{call_idx}] {tool}")
                lines.append(f"      Query: \"{query}\"")
                lines.append(f"      Results: {result_count}개 ({elapsed:.1f}ms)")

                # 문서 목록
                docs = call.get("documents", [])
                if docs:
                    for doc in docs:
                        rank = doc.get("rank", "?")
                        fname = doc.get("file_name", "unknown")
                        score = doc.get("score", 0)
                        preview = doc.get("text_preview", "")[:60]
                        lines.append(f"        #{rank} [{score:.3f}] {fname}")
                        lines.append(f"            \"{preview}...\"")

                lines.append("")

        # Agent 답변 요약
        answer = m.get("answer_agent", "")
        answer_preview = answer[:200] + "..." if len(answer) > 200 else answer
        lines.append(f"  → 답변: {answer_preview}")
        lines.append(f"  → 정확도: {m.get('accuracy_agent', 0)*100:.0f}%")
        lines.append("")

    # 파일 저장
    filename = f"{run_id}_agent_calls.log"
    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


# =============================================================================
# 출력
# =============================================================================


def print_comparison_summary(merged: list[dict]) -> None:
    """비교 결과 요약 출력"""
    stats = calculate_comparison_stats(merged)

    print("\n" + "=" * 70)
    print("📊 Basic vs Agent 비교 결과")
    print("=" * 70)

    print(f"\n총 질문 수: {stats['total_questions']}")

    print("\n┌──────────────────────────────────────────────────────────────────┐")
    print("│                         전체 비교                                │")
    print("├──────────────────────────────────────────────────────────────────┤")
    print(f"│  {'항목':<20} {'Basic':>15} {'Agent':>15} {'차이':>12} │")
    print("├──────────────────────────────────────────────────────────────────┤")
    print(
        f"│  {'평균 레이턴시 (ms)':<20} {stats['basic']['avg_latency_ms']:>15,.1f} {stats['agent']['avg_latency_ms']:>15,.1f} {stats['latency_diff_ms']:>+12,.1f} │"
    )
    print(
        f"│  {'입력 토큰':<20} {stats['basic']['tokens']['input']:>15,} {stats['agent']['tokens']['input']:>15,} {stats['token_diff']['input']:>+12,} │"
    )
    print(
        f"│  {'출력 토큰':<20} {stats['basic']['tokens']['output']:>15,} {stats['agent']['tokens']['output']:>15,} {stats['token_diff']['output']:>+12,} │"
    )
    print(
        f"│  {'총 토큰':<20} {stats['basic']['tokens']['total']:>15,} {stats['agent']['tokens']['total']:>15,} {stats['token_diff']['total']:>+12,} │"
    )
    print(
        f"│  {'비용 (USD)':<20} {'$' + format(stats['basic']['cost_usd'], '.4f'):>15} {'$' + format(stats['agent']['cost_usd'], '.4f'):>15} {'$' + format(stats['cost_diff_usd'], '+.4f'):>12} │"
    )
    print(
        f"│  {'비용 (KRW)':<20} {'₩' + format(int(stats['basic']['cost_krw']), ','):>15} {'₩' + format(int(stats['agent']['cost_krw']), ','):>15} {'₩' + format(int(stats['cost_diff_krw']), '+,'):>12} │"
    )
    print("└──────────────────────────────────────────────────────────────────┘")

    # 정확도 통계
    if stats.get("accuracy"):
        acc = stats["accuracy"]
        print("\n┌──────────────────────────────────────────────────────────────────┐")
        print("│                         정확도 (Key Facts)                       │")
        print("├──────────────────────────────────────────────────────────────────┤")
        print(f"│  Basic: 평균 {acc['basic_avg']*100:.1f}%, 완벽 매칭 {acc['basic_perfect']}개                            │")
        print(f"│  Agent: 평균 {acc['agent_avg']*100:.1f}%, 완벽 매칭 {acc['agent_perfect']}개                            │")
        print("└──────────────────────────────────────────────────────────────────┘")

    # 효율성 지표
    if stats.get("efficiency"):
        eff = stats["efficiency"]
        print("\n┌──────────────────────────────────────────────────────────────────┐")
        print("│                         효율성 지표                              │")
        print("├──────────────────────────────────────────────────────────────────┤")
        if "basic" in eff:
            print(f"│  Basic: {eff['basic']['tokens_per_fact']:.0f} tokens/fact, "
                  f"{eff['basic']['latency_per_fact_ms']:.0f}ms/fact, "
                  f"₩{eff['basic']['cost_per_fact_krw']:.2f}/fact     │")
        if "agent" in eff:
            print(f"│  Agent: {eff['agent']['tokens_per_fact']:.0f} tokens/fact, "
                  f"{eff['agent']['latency_per_fact_ms']:.0f}ms/fact, "
                  f"₩{eff['agent']['cost_per_fact_krw']:.2f}/fact     │")
        print("└──────────────────────────────────────────────────────────────────┘")

    print("\n레벨별 레이턴시 비교:")
    for level, data in stats["by_level"].items():
        basic_avg = data["basic_avg_latency_ms"]
        agent_avg = data["agent_avg_latency_ms"]
        diff = data["latency_diff_ms"]
        ratio = agent_avg / basic_avg if basic_avg > 0 else 0
        print(f"  Level {level}: Basic {basic_avg:,.0f}ms → Agent {agent_avg:,.0f}ms ({diff:+,.0f}ms, {ratio:.1f}x)")

    print("=" * 70)


# =============================================================================
# HTML 리포트 생성
# =============================================================================


def generate_comparison_report(
    merged: list[dict],
    run_id: str,
    output_dir: Path = RESULTS_DIR,
) -> Path:
    """비교 결과 HTML 리포트 생성"""
    stats = calculate_comparison_stats(merged)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG 비교 평가 - {run_id}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f5f5f5; padding: 20px; line-height: 1.6; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}

        h1 {{ color: #333; margin-bottom: 10px; }}
        .run-id {{ color: #666; font-size: 14px; margin-bottom: 30px; }}

        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-card.basic {{ border-left: 4px solid #4CAF50; }}
        .stat-card.agent {{ border-left: 4px solid #2196F3; }}
        .stat-card.diff {{ border-left: 4px solid #FF9800; }}
        .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .stat-value {{ font-size: 28px; font-weight: bold; color: #333; }}
        .stat-unit {{ font-size: 14px; color: #999; }}

        .level-chart {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 30px; }}
        .level-chart h2 {{ margin-bottom: 20px; font-size: 18px; }}
        .level-row {{ display: flex; align-items: center; margin-bottom: 15px; }}
        .level-label {{ width: 80px; font-weight: bold; }}
        .level-bars {{ flex: 1; display: flex; flex-direction: column; gap: 4px; }}
        .bar-container {{ display: flex; align-items: center; }}
        .bar {{ height: 24px; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; color: white; font-size: 12px; min-width: 60px; }}
        .bar.basic {{ background: #4CAF50; }}
        .bar.agent {{ background: #2196F3; }}
        .bar-label {{ margin-left: 10px; font-size: 12px; color: #666; }}

        .questions {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .questions h2 {{ margin-bottom: 20px; font-size: 18px; }}

        .question-card {{ border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 15px; overflow: hidden; }}
        .question-header {{ background: #fafafa; padding: 15px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }}
        .question-header:hover {{ background: #f0f0f0; }}
        .question-meta {{ display: flex; gap: 10px; align-items: center; }}
        .question-id {{ font-weight: bold; color: #333; }}
        .question-level {{ font-size: 12px; padding: 2px 8px; border-radius: 4px; background: #e0e0e0; }}
        .question-level.l1 {{ background: #E8F5E9; color: #2E7D32; }}
        .question-level.l2 {{ background: #E3F2FD; color: #1565C0; }}
        .question-level.l3 {{ background: #FFF3E0; color: #E65100; }}
        .question-level.l4 {{ background: #FCE4EC; color: #C2185B; }}
        .question-text {{ flex: 1; margin-left: 15px; color: #333; }}
        .question-stats {{ display: flex; gap: 15px; font-size: 12px; color: #666; }}

        .question-body {{ padding: 15px; display: none; border-top: 1px solid #e0e0e0; }}
        .question-card.open .question-body {{ display: block; }}

        .answer-compare {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 15px; }}
        .answer-box {{ padding: 15px; border-radius: 8px; }}
        .answer-box.basic {{ background: #E8F5E9; }}
        .answer-box.agent {{ background: #E3F2FD; }}
        .answer-box.expected {{ background: #FFF8E1; grid-column: 1 / -1; }}
        .answer-label {{ font-size: 12px; font-weight: bold; color: #666; margin-bottom: 8px; text-transform: uppercase; }}
        .answer-content {{ font-size: 14px; white-space: pre-wrap; }}

        .key-facts {{ margin-top: 10px; }}
        .key-facts-label {{ font-size: 12px; color: #666; margin-bottom: 5px; }}
        .key-fact {{ display: inline-block; font-size: 12px; padding: 2px 8px; margin: 2px; background: #e0e0e0; border-radius: 4px; }}

        .toggle-icon {{ transition: transform 0.2s; }}
        .question-card.open .toggle-icon {{ transform: rotate(180deg); }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Basic vs Agent RAG 비교 평가</h1>
        <div class="run-id">Run ID: {run_id}</div>

        <div class="stats-grid">
            <div class="stat-card basic">
                <div class="stat-label">Basic 평균 레이턴시</div>
                <div class="stat-value">{stats["basic"]["avg_latency_ms"]:,.0f}<span class="stat-unit">ms</span></div>
            </div>
            <div class="stat-card agent">
                <div class="stat-label">Agent 평균 레이턴시</div>
                <div class="stat-value">{stats["agent"]["avg_latency_ms"]:,.0f}<span class="stat-unit">ms</span></div>
            </div>
            <div class="stat-card diff">
                <div class="stat-label">레이턴시 차이</div>
                <div class="stat-value">{stats["latency_diff_ms"]:+,.0f}<span class="stat-unit">ms</span></div>
            </div>
            <div class="stat-card basic">
                <div class="stat-label">Basic 총 토큰</div>
                <div class="stat-value">{stats["basic"]["tokens"]["total"]:,}</div>
            </div>
            <div class="stat-card agent">
                <div class="stat-label">Agent 총 토큰</div>
                <div class="stat-value">{stats["agent"]["tokens"]["total"]:,}</div>
            </div>
            <div class="stat-card diff">
                <div class="stat-label">토큰 차이</div>
                <div class="stat-value">{stats["token_diff"]["total"]:+,}</div>
            </div>
            <div class="stat-card basic">
                <div class="stat-label">Basic 비용</div>
                <div class="stat-value">${stats["basic"]["cost_usd"]:.4f}<span class="stat-unit"> (₩{int(stats["basic"]["cost_krw"]):,})</span></div>
            </div>
            <div class="stat-card agent">
                <div class="stat-label">Agent 비용</div>
                <div class="stat-value">${stats["agent"]["cost_usd"]:.4f}<span class="stat-unit"> (₩{int(stats["agent"]["cost_krw"]):,})</span></div>
            </div>
            <div class="stat-card diff">
                <div class="stat-label">비용 차이</div>
                <div class="stat-value">${stats["cost_diff_usd"]:+.4f}<span class="stat-unit"> (₩{int(stats["cost_diff_krw"]):+,})</span></div>
            </div>
        </div>

        <div class="level-chart">
            <h2>레벨별 레이턴시 비교</h2>
            {generate_level_bars(stats)}
        </div>

        <div class="questions">
            <h2>질문별 상세 비교 ({len(merged)}개)</h2>
            {generate_question_cards(merged)}
        </div>
    </div>

    <script>
        document.querySelectorAll('.question-header').forEach(header => {{
            header.addEventListener('click', () => {{
                header.parentElement.classList.toggle('open');
            }});
        }});
    </script>
</body>
</html>"""

    output_path = output_dir / f"{run_id}_comparison.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def generate_level_bars(stats: dict) -> str:
    """레벨별 막대 차트 HTML 생성"""
    max_latency = max(
        max(d["basic_avg_latency_ms"] for d in stats["by_level"].values()),
        max(d["agent_avg_latency_ms"] for d in stats["by_level"].values()),
    )

    html = ""
    for level, data in stats["by_level"].items():
        basic_width = (data["basic_avg_latency_ms"] / max_latency * 100) if max_latency > 0 else 0
        agent_width = (data["agent_avg_latency_ms"] / max_latency * 100) if max_latency > 0 else 0

        html += f"""
        <div class="level-row">
            <div class="level-label">Level {level}</div>
            <div class="level-bars">
                <div class="bar-container">
                    <div class="bar basic" style="width: {basic_width}%">{data["basic_avg_latency_ms"]:,.0f}ms</div>
                    <span class="bar-label">Basic</span>
                </div>
                <div class="bar-container">
                    <div class="bar agent" style="width: {agent_width}%">{data["agent_avg_latency_ms"]:,.0f}ms</div>
                    <span class="bar-label">Agent</span>
                </div>
            </div>
        </div>
        """

    return html


def generate_question_cards(merged: list[dict]) -> str:
    """질문 카드 HTML 생성"""
    html = ""
    for m in merged:
        level_class = f"l{m['level']}"
        key_facts_html = ""
        if m.get("key_facts"):
            facts = "".join(f'<span class="key-fact">{f}</span>' for f in m["key_facts"])
            key_facts_html = f'<div class="key-facts"><div class="key-facts-label">핵심 정보:</div>{facts}</div>'

        html += f"""
        <div class="question-card">
            <div class="question-header">
                <div class="question-meta">
                    <span class="question-id">Q{m["id"]}</span>
                    <span class="question-level {level_class}">Level {m["level"]}</span>
                </div>
                <div class="question-text">{m["question"]}</div>
                <div class="question-stats">
                    <span>Basic: {m["latency_basic_ms"]:,.0f}ms</span>
                    <span>Agent: {m["latency_agent_ms"]:,.0f}ms</span>
                </div>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="question-body">
                <div class="answer-box expected">
                    <div class="answer-label">📌 예상 정답</div>
                    <div class="answer-content">{m["expected_answer"]}</div>
                    {key_facts_html}
                </div>
                <div class="answer-compare">
                    <div class="answer-box basic">
                        <div class="answer-label">🟢 Basic RAG ({m["latency_basic_ms"]:,.0f}ms, {m["tokens_basic"]["total"]:,} tokens, 정확도: {m["accuracy_basic"]*100:.0f}%)</div>
                        <div class="answer-content">{m["answer_basic"]}</div>
                    </div>
                    <div class="answer-box agent">
                        <div class="answer-label">🔵 Agent RAG ({m["latency_agent_ms"]:,.0f}ms, {m["tokens_agent"]["total"]:,} tokens, 정확도: {m["accuracy_agent"]*100:.0f}%)</div>
                        <div class="answer-content">{m["answer_agent"]}</div>
                    </div>
                </div>
            </div>
        </div>
        """

    return html


# =============================================================================
# 메인
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Basic vs Agent RAG 비교 평가")
    parser.add_argument(
        "--mode",
        choices=["basic", "agent", "both"],
        default="both",
        help="실행할 모드 (기본: both)",
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
        "--project-id",
        type=int,
        default=334,
        help="프로젝트 ID (기본: 334)",
    )
    parser.add_argument(
        "--compare-only",
        nargs=2,
        metavar=("BASIC_JSON", "AGENT_JSON"),
        help="기존 결과 파일로 비교만 실행",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="설정만 출력하고 종료",
    )

    args = parser.parse_args()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 기존 결과로 비교만
    if args.compare_only:
        basic_path, agent_path = args.compare_only
        with open(basic_path, encoding="utf-8") as f:
            basic_data = json.load(f)
        with open(agent_path, encoding="utf-8") as f:
            agent_data = json.load(f)

        merged = merge_results(basic_data["results"], agent_data["results"])

        # 저장 및 출력
        comparison_path = save_comparison(merged, run_id)
        html_path = generate_comparison_report(merged, run_id)
        log_path = save_agent_call_log(merged, run_id)

        print_comparison_summary(merged)
        print(f"\n💾 비교 결과: {comparison_path}")
        print(f"📊 HTML 리포트: {html_path}")
        print(f"📝 Agent 호출 로그: {log_path}")
        return

    # 질문 로드 및 필터
    questions = load_questions()
    question_ids = [int(x) for x in args.questions.split(",")] if args.questions else None
    questions = filter_questions(questions, question_ids, args.level)

    if not questions:
        print("❌ 실행할 질문이 없습니다.")
        return

    # dry-run
    if args.dry_run:
        print(f"\n🔧 실행 설정")
        print(f"  모드: {args.mode}")
        print(f"  질문 수: {len(questions)}")
        print(f"  프로젝트 ID: {args.project_id}")
        print("\n실행 대상 질문:")
        for q in questions:
            print(f"  [{q['id']}] Level {q['level']}: {q['question'][:40]}...")
        return

    print(f"\n📝 {len(questions)}개 질문 실행 예정")

    basic_results = []
    agent_results = []

    # 실행
    if args.mode in ["basic", "both"]:
        basic_results = run_mode("basic", questions, args.project_id)
        basic_path = save_results(basic_results, "basic", run_id)
        print(f"\n💾 Basic 결과: {basic_path}")

    if args.mode in ["agent", "both"]:
        agent_results = run_mode("agent", questions, args.project_id)
        agent_path = save_results(agent_results, "agent", run_id)
        print(f"\n💾 Agent 결과: {agent_path}")

    # 비교
    if args.mode == "both" and basic_results and agent_results:
        merged = merge_results(basic_results, agent_results)
        comparison_path = save_comparison(merged, run_id)
        html_path = generate_comparison_report(merged, run_id)
        log_path = save_agent_call_log(merged, run_id)

        print_comparison_summary(merged)
        print(f"\n💾 비교 결과: {comparison_path}")
        print(f"📊 HTML 리포트: {html_path}")
        print(f"📝 Agent 호출 로그: {log_path}")


if __name__ == "__main__":
    main()
