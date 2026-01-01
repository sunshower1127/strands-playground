"""RAG 테스트 결과 HTML 리포트 생성

JSON 결과 파일을 보기 좋은 HTML 리포트로 변환합니다.

Usage:
    uv run python scripts/generate_report.py data/results/20260101_174743_minimal.json
    uv run python scripts/generate_report.py data/results/*.json  # 여러 파일
"""

import argparse
import json
from pathlib import Path

# =============================================================================
# HTML 템플릿
# =============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG 테스트 리포트 - {run_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}

        /* 헤더 */
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
        }}
        .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.9; font-size: 14px; }}
        .header .config {{
            background: rgba(255,255,255,0.1);
            padding: 10px 15px;
            border-radius: 8px;
            margin-top: 15px;
            font-family: monospace;
            font-size: 12px;
        }}

        /* 요약 카드 */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .stat-card .label {{ color: #666; font-size: 13px; margin-bottom: 5px; }}
        .stat-card .value {{ font-size: 28px; font-weight: 600; color: #333; }}
        .stat-card .sub {{ font-size: 12px; color: #999; margin-top: 5px; }}

        /* 타이밍 분석 */
        .section {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .section h2 {{
            font-size: 18px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }}

        .timing-bar {{
            display: flex;
            align-items: center;
            margin-bottom: 12px;
        }}
        .timing-bar .name {{
            width: 120px;
            font-size: 13px;
            color: #555;
        }}
        .timing-bar .bar-container {{
            flex: 1;
            height: 24px;
            background: #f0f0f0;
            border-radius: 4px;
            overflow: hidden;
            margin: 0 15px;
        }}
        .timing-bar .bar {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 4px;
            transition: width 0.3s;
        }}
        .timing-bar .time {{
            width: 80px;
            text-align: right;
            font-size: 13px;
            font-weight: 500;
        }}

        /* 질문별 상세 */
        .question-card {{
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            margin-bottom: 15px;
            overflow: hidden;
        }}
        .question-card summary {{
            padding: 15px 20px;
            background: #fafafa;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .question-card summary:hover {{ background: #f5f5f5; }}
        .question-card[open] summary {{ border-bottom: 1px solid #e0e0e0; }}

        .question-card .badge {{
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-level {{ background: #e3f2fd; color: #1976d2; }}
        .badge-category {{ background: #f3e5f5; color: #7b1fa2; }}

        .question-card .question-text {{
            flex: 1;
            font-weight: 500;
        }}
        .question-card .latency {{
            font-size: 13px;
            color: #666;
        }}

        .question-detail {{
            padding: 20px;
        }}
        .answer-section {{
            margin-bottom: 20px;
        }}
        .answer-section h4 {{
            font-size: 13px;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
        }}
        .answer-box {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            font-size: 14px;
            white-space: pre-wrap;
            border-left: 3px solid #667eea;
        }}
        .answer-box.expected {{
            border-left-color: #4caf50;
            background: #f1f8e9;
        }}

        .key-facts {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }}
        .key-fact {{
            background: #e8f5e9;
            color: #2e7d32;
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 12px;
        }}

        .sources {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .source {{
            background: #fff3e0;
            color: #e65100;
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 12px;
        }}

        .timing-detail {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }}
        .timing-item {{
            background: #f5f5f5;
            padding: 10px;
            border-radius: 6px;
            text-align: center;
        }}
        .timing-item .name {{ font-size: 11px; color: #666; }}
        .timing-item .value {{ font-size: 16px; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""


# =============================================================================
# 렌더링 함수
# =============================================================================


def render_header(data: dict) -> str:
    """헤더 섹션 렌더링"""
    config = data["config"]
    config_str = " | ".join(f"{k}: {v}" for k, v in config.items() if v is not None)

    return f"""
    <div class="header">
        <h1>RAG 테스트 리포트</h1>
        <div class="meta">Run ID: {data['run_id']} | Pipeline: {config['name']}</div>
        <div class="config">{config_str}</div>
    </div>
    """


def render_summary(data: dict) -> str:
    """요약 통계 렌더링"""
    summary = data["summary"]

    level_stats = ""
    for level, stats in summary.get("by_level", {}).items():
        level_stats += f"L{level}: {stats['count']}개 ({stats['avg_latency_ms']:.0f}ms) | "
    level_stats = level_stats.rstrip(" | ")

    return f"""
    <div class="summary-grid">
        <div class="stat-card">
            <div class="label">총 질문 수</div>
            <div class="value">{summary['total_questions']}</div>
            <div class="sub">{level_stats}</div>
        </div>
        <div class="stat-card">
            <div class="label">평균 레이턴시</div>
            <div class="value">{summary['avg_latency_ms']:.1f}<span style="font-size:14px">ms</span></div>
            <div class="sub">최소 {summary['min_latency_ms']:.0f}ms / 최대 {summary['max_latency_ms']:.0f}ms</div>
        </div>
        <div class="stat-card">
            <div class="label">총 토큰</div>
            <div class="value">{summary['total_tokens']:,}</div>
            <div class="sub">입력 {summary['total_input_tokens']:,} / 출력 {summary['total_output_tokens']:,}</div>
        </div>
        <div class="stat-card">
            <div class="label">모델</div>
            <div class="value" style="font-size:16px">{data['results'][0].get('model', 'N/A')}</div>
        </div>
    </div>
    """


def render_timing_analysis(data: dict) -> str:
    """평균 타이밍 분석 렌더링"""
    # 모든 결과의 타이밍 집계
    timing_sums: dict[str, float] = {}
    timing_counts: dict[str, int] = {}

    for result in data["results"]:
        for name, ms in result.get("timings", {}).items():
            timing_sums[name] = timing_sums.get(name, 0) + ms
            timing_counts[name] = timing_counts.get(name, 0) + 1

    if not timing_sums:
        return ""

    # 평균 계산
    timing_avgs = {name: timing_sums[name] / timing_counts[name] for name in timing_sums}
    max_time = max(timing_avgs.values()) if timing_avgs else 1

    # 순서 정렬 (파이프라인 순서대로)
    order = ["query_enhance", "preprocess", "embedding", "query_build", "search", "filter", "chunk_expand", "context_build", "prompt_render", "llm"]
    sorted_timings = [(name, timing_avgs[name]) for name in order if name in timing_avgs]

    bars_html = ""
    for name, avg_ms in sorted_timings:
        pct = (avg_ms / max_time) * 100
        bars_html += f"""
        <div class="timing-bar">
            <div class="name">{name}</div>
            <div class="bar-container">
                <div class="bar" style="width: {pct}%"></div>
            </div>
            <div class="time">{avg_ms:.1f}ms</div>
        </div>
        """

    return f"""
    <div class="section">
        <h2>평균 단계별 소요시간</h2>
        {bars_html}
    </div>
    """


def render_questions(data: dict) -> str:
    """질문별 상세 렌더링"""
    cards_html = ""

    for r in data["results"]:
        # 소스 목록
        sources_html = ""
        for s in r.get("sources", [])[:5]:
            sources_html += f'<span class="source">{s["file_name"]} ({s["score"]:.2f})</span>'

        # 타이밍 상세
        timing_html = ""
        for name, ms in r.get("timings", {}).items():
            timing_html += f"""
            <div class="timing-item">
                <div class="name">{name}</div>
                <div class="value">{ms:.0f}ms</div>
            </div>
            """

        # key_facts
        facts_html = ""
        for fact in r.get("key_facts", []):
            facts_html += f'<span class="key-fact">{fact}</span>'

        cards_html += f"""
        <details class="question-card">
            <summary>
                <span class="badge badge-level">Level {r['level']}</span>
                <span class="badge badge-category">{r['category']}</span>
                <span class="question-text">{r['question']}</span>
                <span class="latency">{r['latency_ms']:.0f}ms</span>
            </summary>
            <div class="question-detail">
                <div class="answer-section">
                    <h4>예상 정답</h4>
                    <div class="answer-box expected">{r.get('expected_answer', 'N/A')}</div>
                    <div class="key-facts">{facts_html}</div>
                </div>
                <div class="answer-section">
                    <h4>실제 답변</h4>
                    <div class="answer-box">{r['answer']}</div>
                </div>
                <div class="answer-section">
                    <h4>소스 문서</h4>
                    <div class="sources">{sources_html if sources_html else '<span style="color:#999">없음</span>'}</div>
                </div>
                <div class="timing-detail">
                    {timing_html}
                </div>
            </div>
        </details>
        """

    return f"""
    <div class="section">
        <h2>질문별 상세 결과</h2>
        {cards_html}
    </div>
    """


def generate_html_report(json_path: Path) -> Path:
    """JSON 결과 → HTML 리포트 생성"""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    content = (
        render_header(data)
        + render_summary(data)
        + render_timing_analysis(data)
        + render_questions(data)
    )

    html = HTML_TEMPLATE.format(run_id=data["run_id"], content=content)

    output_path = json_path.with_suffix(".html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


# =============================================================================
# 메인
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="RAG 결과 HTML 리포트 생성")
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="JSON 결과 파일 경로",
    )

    args = parser.parse_args()

    for json_path in args.files:
        if not json_path.exists():
            print(f"❌ 파일 없음: {json_path}")
            continue

        output_path = generate_html_report(json_path)
        print(f"✅ 리포트 생성: {output_path}")


if __name__ == "__main__":
    main()
