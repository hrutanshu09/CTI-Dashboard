import argparse
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "evaluation" / "results"
DEFAULT_RETR = RESULTS_DIR / "retrieval_metrics.json"
DEFAULT_GEN = RESULTS_DIR / "generation_metrics.json"
DEFAULT_REPORT = RESULTS_DIR / "validation_report.md"


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def format_retrieval(retr: dict | None):
    if not retr:
        return ["## Retrieval Metrics", "- Retrieval metrics file not found."]

    s = retr.get("summary", {})
    k = s.get("k", 5)
    return [
        "## Retrieval Metrics",
        f"- Queries used: {s.get('queries_used', 0)} / {s.get('queries_total', 0)}",
        f"- Avg Recall@{k}: {s.get(f'avg_recall@{k}', 0)}",
        f"- Avg Precision@{k}: {s.get(f'avg_precision@{k}', 0)}",
        f"- MRR: {s.get('mrr', 0)}",
        f"- Skipped (missing expected_doc_ids): {s.get('queries_skipped_missing_expected_doc_ids', 0)}",
    ]


def format_generation(gen: dict | None):
    if not gen:
        return ["## Generation Metrics", "- Generation metrics file not found."]

    s = gen.get("summary", {})
    lines = [
        "## Generation Metrics",
        f"- Mode: {s.get('mode', '-')}",
        f"- Queries model run: {s.get('queries_model_run', 0)} / {s.get('queries_total', 0)}",
    ]

    if s.get("avg_auto_correctness") is not None:
        lines.append(f"- Avg Auto Correctness: {s.get('avg_auto_correctness')}")

    lines.append("- Human rubric scores should be filled in generation_metrics.json for final presentation.")
    return lines


def top_errors(section: dict | None, section_name: str):
    if not section:
        return []

    rows = section.get("per_query", [])
    errs = [r for r in rows if r.get("status") == "error"]
    if not errs:
        return []

    lines = [f"## {section_name} Errors"]
    for e in errs[:10]:
        lines.append(f"- {e.get('id', '-')} : {e.get('error', 'unknown error')}")
    return lines


def main():
    parser = argparse.ArgumentParser(description="Build combined RAG validation report")
    parser.add_argument("--retrieval", type=Path, default=DEFAULT_RETR)
    parser.add_argument("--generation", type=Path, default=DEFAULT_GEN)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    retr = load_json(args.retrieval)
    gen = load_json(args.generation)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# RAG Validation Report",
        "",
        f"Generated at: {now}",
        "",
    ]
    lines.extend(format_retrieval(retr))
    lines.append("")
    lines.extend(format_generation(gen))
    lines.append("")
    lines.extend(top_errors(retr, "Retrieval"))
    lines.append("")
    lines.extend(top_errors(gen, "Generation"))
    lines.append("")
    lines.append("## Notes")
    lines.append("- Retrieval metrics are meaningful only when expected_doc_ids are populated in gold_queries.jsonl.")
    lines.append("- Generation metrics for presentation should include human rubric scoring.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print("Saved:", args.out)


if __name__ == "__main__":
    main()
