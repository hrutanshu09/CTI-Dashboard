import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "evaluation" / "gold_queries.jsonl"
DEFAULT_CORE = ROOT / "evaluation" / "gold_queries_core.jsonl"
DEFAULT_STRESS = ROOT / "evaluation" / "gold_queries_stress.jsonl"

AMBIGUOUS_TERMS = {
    "classify",
    "prioritize",
    "distinguish",
    "evidence",
    "evaluate",
    "metrics",
    "risk",
    "attribution",
    "how",
    "why",
}


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


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def is_stress_query(row: dict, max_core_words: int, min_expected_points: int) -> bool:
    q = str(row.get("query", "")).strip().lower()
    words = [w for w in q.replace("?", "").split() if w]
    points = row.get("expected_points", []) or []

    term_hit = any(t in words for t in AMBIGUOUS_TERMS)
    too_long = len(words) > max_core_words
    low_points = len(points) < min_expected_points

    # Stress if broadly phrased or underspecified.
    return term_hit or too_long or low_points


def main():
    parser = argparse.ArgumentParser(description="Build core/stress benchmark splits from gold queries")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--core-out", type=Path, default=DEFAULT_CORE)
    parser.add_argument("--stress-out", type=Path, default=DEFAULT_STRESS)
    parser.add_argument("--max-core-words", type=int, default=12)
    parser.add_argument("--min-expected-points", type=int, default=3)
    args = parser.parse_args()

    if not args.gold.exists():
        raise FileNotFoundError(f"Gold file missing: {args.gold}")

    rows = load_jsonl(args.gold)
    core = []
    stress = []

    for row in rows:
        target = stress if is_stress_query(row, args.max_core_words, args.min_expected_points) else core
        target.append(row)

    args.core_out.parent.mkdir(parents=True, exist_ok=True)
    args.stress_out.parent.mkdir(parents=True, exist_ok=True)

    write_jsonl(args.core_out, core)
    write_jsonl(args.stress_out, stress)

    print(f"Saved core: {args.core_out} (rows={len(core)})")
    print(f"Saved stress: {args.stress_out} (rows={len(stress)})")


if __name__ == "__main__":
    main()
