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
                    # 모드별 추가 정보
                    "sources": result.sources if mode == "basic" else [],
                    "tool_calls": result.tool_calls if mode == "agent" else [],
                    "timings": result.timings if mode == "basic" else {},
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

        merged.append(
            {
                "id": q_id,
                "level": b["level"],
                "category": b["category"],
                "question": b["question"],
                "expected_answer": b.get("expected_answer", ""),
                "key_facts": b.get("key_facts", []),
                # Basic 결과
                "answer_basic": b["answer"],
                "latency_basic_ms": b["latency_ms"],
                "tokens_basic": b["input_tokens"] + b["output_tokens"],
                "sources_basic": b.get("sources", []),
                # Agent 결과
                "answer_agent": a.get("answer", "N/A"),
                "latency_agent_ms": a.get("latency_ms", 0),
                "tokens_agent": a.get("input_tokens", 0) + a.get("output_tokens", 0),
                "tool_calls": a.get("tool_calls", []),
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

    basic_tokens = sum(m["tokens_basic"] for m in merged)
    agent_tokens = sum(m["tokens_agent"] for m in merged)

    # 비용 계산
    basic_input = sum(m.get("input_basic", 0) for m in merged)
    basic_output = sum(m.get("output_basic", 0) for m in merged)
    agent_input = sum(m.get("input_agent", 0) for m in merged)
    agent_output = sum(m.get("output_agent", 0) for m in merged)

    # tokens_basic/agent에서 대략 추정 (input:output = 9:1 가정)
    if basic_input == 0 and basic_tokens > 0:
        basic_input = int(basic_tokens * 0.9)
        basic_output = basic_tokens - basic_input
    if agent_input == 0 and agent_tokens > 0:
        agent_input = int(agent_tokens * 0.9)
        agent_output = agent_tokens - agent_input

    basic_cost = calculate_cost(basic_input, basic_output)
    agent_cost = calculate_cost(agent_input, agent_output)

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
            "total_tokens": basic_tokens,
            "cost_usd": round(basic_cost["total_usd"], 4),
            "cost_krw": round(basic_cost["total_krw"], 0),
        },
        "agent": {
            "avg_latency_ms": round(sum(agent_latencies) / len(agent_latencies), 1) if agent_latencies else 0,
            "total_tokens": agent_tokens,
            "cost_usd": round(agent_cost["total_usd"], 4),
            "cost_krw": round(agent_cost["total_krw"], 0),
        },
        "latency_diff_ms": round(
            (sum(agent_latencies) / len(agent_latencies) if agent_latencies else 0)
            - (sum(basic_latencies) / len(basic_latencies) if basic_latencies else 0),
            1,
        ),
        "token_diff": agent_tokens - basic_tokens,
        "cost_diff_usd": round(agent_cost["total_usd"] - basic_cost["total_usd"], 4),
        "cost_diff_krw": round(agent_cost["total_krw"] - basic_cost["total_krw"], 0),
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
        f"│  {'총 토큰':<20} {stats['basic']['total_tokens']:>15,} {stats['agent']['total_tokens']:>15,} {stats['token_diff']:>+12,} │"
    )
    print(
        f"│  {'비용 (USD)':<20} {'$' + format(stats['basic']['cost_usd'], '.4f'):>15} {'$' + format(stats['agent']['cost_usd'], '.4f'):>15} {'$' + format(stats['cost_diff_usd'], '+.4f'):>12} │"
    )
    print(
        f"│  {'비용 (KRW)':<20} {'₩' + format(int(stats['basic']['cost_krw']), ','):>15} {'₩' + format(int(stats['agent']['cost_krw']), ','):>15} {'₩' + format(int(stats['cost_diff_krw']), '+,'):>12} │"
    )
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
                <div class="stat-value">{stats["basic"]["total_tokens"]:,}</div>
            </div>
            <div class="stat-card agent">
                <div class="stat-label">Agent 총 토큰</div>
                <div class="stat-value">{stats["agent"]["total_tokens"]:,}</div>
            </div>
            <div class="stat-card diff">
                <div class="stat-label">토큰 차이</div>
                <div class="stat-value">{stats["token_diff"]:+,}</div>
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
                        <div class="answer-label">🟢 Basic RAG ({m["latency_basic_ms"]:,.0f}ms, {m["tokens_basic"]:,} tokens)</div>
                        <div class="answer-content">{m["answer_basic"]}</div>
                    </div>
                    <div class="answer-box agent">
                        <div class="answer-label">🔵 Agent RAG ({m["latency_agent_ms"]:,.0f}ms, {m["tokens_agent"]:,} tokens)</div>
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

        print_comparison_summary(merged)
        print(f"\n💾 비교 결과: {comparison_path}")
        print(f"📊 HTML 리포트: {html_path}")
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

        print_comparison_summary(merged)
        print(f"\n💾 비교 결과: {comparison_path}")
        print(f"📊 HTML 리포트: {html_path}")


if __name__ == "__main__":
    main()
