import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "evaluation" / "gold_queries.jsonl"
DEFAULT_OUT = ROOT / "evaluation" / "results" / "generation_metrics.json"


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSONL at line {line_no}: {e}") from e
    return rows


def keyword_coverage_score(answer: str, expected_points: list[str]) -> float:
    if not expected_points:
        return 0.0

    answer_l = answer.lower()
    hit = 0
    for p in expected_points:
        p_l = p.lower()
        # lightweight token overlap: at least 2 shared tokens between expected point and answer
        p_tokens = [t for t in p_l.replace("/", " ").replace("-", " ").split() if len(t) > 2]
        overlap = sum(1 for t in set(p_tokens) if t in answer_l)
        if overlap >= 2:
            hit += 1
    return hit / len(expected_points)


def clamp(v: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, v))


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG generation quality")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--run-model", action="store_true", help="Run actual RAG generation using Gemini")
    args = parser.parse_args()

    if not args.gold.exists():
        raise FileNotFoundError(f"Gold file missing: {args.gold}")

    gold = load_jsonl(args.gold)

    analyze_threat = None
    if args.run_model:
        import sys
        sys.path.insert(0, str(ROOT))
        from services.rag_services import analyze_threat as _analyze_threat  # noqa: E402
        analyze_threat = _analyze_threat

    per_query = []
    used = 0

    for item in gold:
        qid = item.get("id")
        query = str(item.get("query", "")).strip()
        expected_points = item.get("expected_points", []) or []

        if not query:
            per_query.append({"id": qid, "status": "skipped_empty_query"})
            continue

        row: dict[str, Any] = {
            "id": qid,
            "query": query,
            "expected_points": expected_points,
            "status": "ok",
        }

        if analyze_threat is None:
            row.update(
                {
                    "mode": "template_only",
                    "answer": "",
                    "sources": [],
                    "auto_correctness": None,
                    "human_scores": {
                        "correctness_0_to_2": None,
                        "groundedness_0_or_1": None,
                        "completeness_0_to_2": None,
                        "actionability_0_to_2": None,
                        "notes": "",
                    },
                }
            )
            per_query.append(row)
            continue

        try:
            result = analyze_threat(query)
            answer = str(result.get("response", ""))
            sources = result.get("sources", []) or []

            auto_correctness = keyword_coverage_score(answer, expected_points)

            row.update(
                {
                    "mode": "model_run",
                    "answer": answer,
                    "sources": sources[: args.k],
                    "auto_correctness": round(clamp(auto_correctness), 4),
                    "human_scores": {
                        "correctness_0_to_2": None,
                        "groundedness_0_or_1": None,
                        "completeness_0_to_2": None,
                        "actionability_0_to_2": None,
                        "notes": "",
                    },
                }
            )
            used += 1
        except Exception as e:
            row.update({"status": "error", "error": str(e), "mode": "model_run"})

        per_query.append(row)

    auto_rows = [r for r in per_query if r.get("mode") == "model_run" and r.get("status") == "ok"]
    avg_auto = (
        sum(r.get("auto_correctness", 0.0) for r in auto_rows) / len(auto_rows)
        if auto_rows
        else 0.0
    )

    summary = {
        "queries_total": len(gold),
        "queries_model_run": used,
        "mode": "model_run" if args.run_model else "template_only",
        "avg_auto_correctness": round(avg_auto, 4) if args.run_model else None,
        "note": "Fill human_scores fields for presentation-grade quality evaluation.",
    }

    output = {
        "summary": summary,
        "per_query": per_query,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Saved:", args.out)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
