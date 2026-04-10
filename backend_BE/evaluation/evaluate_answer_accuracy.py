import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "evaluation" / "gold_queries.jsonl"
DEFAULT_OUT = ROOT / "evaluation" / "results" / "answer_accuracy.json"


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


def point_hit(answer: str, point: str) -> bool:
    answer_l = answer.lower()
    tokens = [t for t in point.lower().replace("/", " ").replace("-", " ").split() if len(t) > 2]
    if not tokens:
        return False
    overlap = sum(1 for t in set(tokens) if t in answer_l)
    return overlap >= 2


def coverage(answer: str, expected_points: list[str]) -> float:
    if not expected_points:
        return 0.0
    hits = sum(1 for p in expected_points if point_hit(answer, p))
    return hits / len(expected_points)


def main():
    parser = argparse.ArgumentParser(description="Compute RAG Answer Accuracy")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--threshold", type=float, default=0.67, help="Coverage threshold to mark an answer as correct")
    parser.add_argument("--k", type=int, default=5, help="Number of sources to keep in output")
    parser.add_argument("--max-retries", type=int, default=2, help="Retries for transient model errors such as 429")
    parser.add_argument("--retry-seconds", type=int, default=30, help="Wait time between retries")
    args = parser.parse_args()

    if not args.gold.exists():
        raise FileNotFoundError(f"Gold file missing: {args.gold}")

    import sys
    sys.path.insert(0, str(ROOT))
    from services.rag_services import analyze_threat  # noqa: E402

    gold = load_jsonl(args.gold)

    total = 0
    success_total = 0
    correct = 0
    errors = 0
    per_query = []

    for item in gold:
        qid = item.get("id")
        query = str(item.get("query", "")).strip()
        expected_points = item.get("expected_points", []) or []

        if not query:
            per_query.append({"id": qid, "status": "skipped_empty_query"})
            continue

        total += 1

        try:
            result = None
            for attempt in range(args.max_retries + 1):
                try:
                    result = analyze_threat(query)
                    break
                except Exception:
                    if attempt < args.max_retries:
                        time.sleep(max(args.retry_seconds, 1))
                    else:
                        raise

            answer = str(result.get("response", ""))
            score = coverage(answer, expected_points)
            is_correct = score >= args.threshold
            success_total += 1
            if is_correct:
                correct += 1

            per_query.append(
                {
                    "id": qid,
                    "query": query,
                    "expected_points": expected_points,
                    "coverage_score": round(score, 4),
                    "is_correct": is_correct,
                    "answer": answer,
                    "sources": (result.get("sources", []) or [])[: args.k],
                    "status": "ok",
                }
            )
        except Exception as e:
            errors += 1
            per_query.append({"id": qid, "query": query, "status": "error", "error": str(e)})

    strict_accuracy = (correct / total) if total else 0.0
    answered_only_accuracy = (correct / success_total) if success_total else 0.0

    output = {
        "summary": {
            "queries_total": len(gold),
            "queries_scored": total,
            "queries_answered_successfully": success_total,
            "errors": errors,
            "threshold": args.threshold,
            "correct_answers": correct,
            "strict_answer_accuracy": round(strict_accuracy, 4),
            "strict_answer_accuracy_percent": round(strict_accuracy * 100, 2),
            "answer_accuracy_on_success": round(answered_only_accuracy, 4),
            "answer_accuracy_on_success_percent": round(answered_only_accuracy * 100, 2),
            "availability_percent": round((success_total / total) * 100, 2) if total else 0.0,
        },
        "per_query": per_query,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Saved:", args.out)
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()
