import argparse
import json
import pickle
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "evaluation" / "gold_queries.jsonl"
DEFAULT_DOC_MAP = ROOT / "rag_store" / "doc_mapping.pkl"
DEFAULT_OUT = ROOT / "evaluation" / "results" / "modular_rag_metrics.json"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
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


def canonical_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "text": doc.get("text", ""),
        "source": doc.get("source", ""),
        "type": doc.get("type", ""),
        "label": doc.get("label", ""),
        "metadata": doc.get("metadata", {}),
    }


def doc_key(doc: Dict[str, Any]) -> str:
    return json.dumps(canonical_doc(doc), sort_keys=True, ensure_ascii=False)


def build_doc_index_map(documents: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    key_to_ids: Dict[str, List[int]] = defaultdict(list)
    for idx, doc in enumerate(documents):
        key_to_ids[doc_key(doc)].append(idx)
    return key_to_ids


def point_hit(answer: str, point: str) -> bool:
    answer_l = answer.lower()
    tokens = [t for t in point.lower().replace("/", " ").replace("-", " ").split() if len(t) > 2]
    if not tokens:
        return False
    overlap = sum(1 for t in set(tokens) if t in answer_l)
    return overlap >= 2


def coverage(answer: str, expected_points: List[str]) -> float:
    if not expected_points:
        return 0.0
    hits = sum(1 for p in expected_points if point_hit(answer, p))
    return hits / len(expected_points)


def build_concise_prompt(query: str, retrieved_docs: List[Dict[str, Any]]) -> str:
    context = "\n\n".join(
        f"[Source {i+1}] {str(doc.get('text', ''))}"
        for i, doc in enumerate(retrieved_docs)
    )
    return (
        "You are a cyber threat analyst.\n"
        "Use only the provided context. If missing, say 'Insufficient context'.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION:\n{query}\n\n"
        "Return concise sections:\n"
        "1) Threat/Behavior (max 2 bullets)\n"
        "2) Key Indicators (max 4 bullets)\n"
        "3) Detection Signals (max 4 bullets)\n"
        "4) Mitigations (max 5 bullets)\n"
        "Do not repeat bullets across sections."
    )


def parse_scenarios(text: str) -> List[Dict[str, Any]]:
    available = {
        "baseline": {
            "scenario_id": "baseline",
            "swap_module": "none",
            "retrieve_mode": "global",
            "k": 10,
            "prompt_variant": "default",
        },
        "swap_retrieval_k5": {
            "scenario_id": "swap_retrieval_k5",
            "swap_module": "retrieval.k",
            "retrieve_mode": "global",
            "k": 5,
            "prompt_variant": "default",
        },
        "swap_retrieval_k15": {
            "scenario_id": "swap_retrieval_k15",
            "swap_module": "retrieval.k",
            "retrieve_mode": "global",
            "k": 15,
            "prompt_variant": "default",
        },
        "swap_prompt_concise": {
            "scenario_id": "swap_prompt_concise",
            "swap_module": "prompt.template",
            "retrieve_mode": "global",
            "k": 10,
            "prompt_variant": "concise",
        },
    }

    requested = [s.strip() for s in text.split(",") if s.strip()]
    if not requested:
        requested = ["baseline", "swap_retrieval_k5", "swap_prompt_concise"]

    unknown = [s for s in requested if s not in available]
    if unknown:
        raise ValueError(
            f"Unknown scenario(s): {unknown}. Available: {sorted(available.keys())}"
        )

    return [available[s] for s in requested]


def safe_generate(
    generate_fn,
    prompt: str,
    max_retries: int,
    retry_seconds: int,
) -> str:
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return str(generate_fn(prompt))
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(max(retry_seconds, 1))
    raise RuntimeError(f"Generation failed after retries: {last_err}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Modular RAG: module swap, cascade degradation, and E2E accuracy."
    )
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--doc-map", type=Path, default=DEFAULT_DOC_MAP)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--threshold", type=float, default=0.67, help="Coverage threshold for correct answer.")
    parser.add_argument(
        "--scenarios",
        type=str,
        default="baseline,swap_retrieval_k5,swap_prompt_concise",
        help="Comma-separated scenarios. Available: baseline,swap_retrieval_k5,swap_retrieval_k15,swap_prompt_concise",
    )
    parser.add_argument("--run-model", action="store_true", help="Run Gemini generation for E2E and cascade metrics.")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-seconds", type=int, default=30)
    args = parser.parse_args()

    if not args.gold.exists():
        raise FileNotFoundError(f"Gold file missing: {args.gold}")
    if not args.doc_map.exists():
        raise FileNotFoundError(f"Doc mapping missing: {args.doc_map}")

    import sys
    sys.path.insert(0, str(ROOT))
    from RAG.retreival import retrieve_context  # noqa: E402
    from RAG.rag_prompt import build_rag_prompt  # noqa: E402

    generate_fn = None
    if args.run_model:
        from core.gemini_client import generate as _generate  # noqa: E402

        generate_fn = _generate

    with args.doc_map.open("rb") as f:
        documents = pickle.load(f)
    key_to_ids = build_doc_index_map(documents)

    gold = load_jsonl(args.gold)
    scenarios = parse_scenarios(args.scenarios)

    all_results: Dict[str, Dict[str, Any]] = {}

    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        per_query = []
        retrieval_used = 0
        retrieval_hits = 0
        answer_used = 0
        answer_success = 0
        answer_correct = 0
        errors = 0

        cascade_counts = {
            "retrieval_ok_answer_ok": 0,
            "retrieval_ok_answer_fail": 0,
            "retrieval_fail_answer_ok": 0,
            "retrieval_fail_answer_fail": 0,
        }

        for item in gold:
            qid = item.get("id")
            query = str(item.get("query", "")).strip()
            expected_doc_ids = item.get("expected_doc_ids", []) or []
            expected_points = item.get("expected_points", []) or []
            report_id = item.get("report_id")

            if not query:
                per_query.append({"id": qid, "status": "skipped_empty_query"})
                continue

            row: Dict[str, Any] = {
                "id": qid,
                "query": query,
                "scenario_id": scenario_id,
                "swap_module": scenario["swap_module"],
                "retrieve_mode": scenario["retrieve_mode"],
                "k": scenario["k"],
                "prompt_variant": scenario["prompt_variant"],
                "status": "ok",
            }

            try:
                retrieved_docs = retrieve_context(
                    query,
                    k=int(scenario["k"]),
                    report_id=report_id,
                    retrieve_mode=str(scenario["retrieve_mode"]),
                )

                retrieved_ids: List[int] = []
                for doc in retrieved_docs:
                    key = doc_key(doc if isinstance(doc, dict) else {"text": str(doc)})
                    candidate_ids = key_to_ids.get(key, [])
                    if candidate_ids:
                        retrieved_ids.append(candidate_ids[0])

                row["retrieved_doc_ids"] = retrieved_ids

                retrieval_hit: Optional[bool] = None
                if expected_doc_ids:
                    retrieval_used += 1
                    expected_set = {int(x) for x in expected_doc_ids}
                    retrieval_hit = len(set(retrieved_ids) & expected_set) > 0
                    if retrieval_hit:
                        retrieval_hits += 1
                    row["retrieval_hit"] = retrieval_hit
                    row["expected_doc_ids"] = sorted(expected_set)
                else:
                    row["retrieval_hit"] = None

                if args.run_model and generate_fn is not None:
                    if scenario["prompt_variant"] == "default":
                        prompt = build_rag_prompt(query, retrieved_docs)
                    else:
                        prompt = build_concise_prompt(query, retrieved_docs)

                    answer = safe_generate(
                        generate_fn,
                        prompt,
                        max_retries=args.max_retries,
                        retry_seconds=args.retry_seconds,
                    )
                    answer_success += 1
                    row["answer"] = answer

                    if expected_points:
                        answer_used += 1
                        score = coverage(answer, expected_points)
                        is_correct = score >= args.threshold
                        if is_correct:
                            answer_correct += 1
                        row["coverage_score"] = round(score, 4)
                        row["is_correct"] = is_correct
                        row["expected_points"] = expected_points
                    else:
                        row["coverage_score"] = None
                        row["is_correct"] = None

                    if expected_doc_ids and expected_points:
                        rh = bool(row.get("retrieval_hit"))
                        ic = bool(row.get("is_correct"))
                        if rh and ic:
                            cascade_counts["retrieval_ok_answer_ok"] += 1
                        elif rh and not ic:
                            cascade_counts["retrieval_ok_answer_fail"] += 1
                        elif not rh and ic:
                            cascade_counts["retrieval_fail_answer_ok"] += 1
                        else:
                            cascade_counts["retrieval_fail_answer_fail"] += 1
                else:
                    row["answer"] = ""
                    row["coverage_score"] = None
                    row["is_correct"] = None

                per_query.append(row)
            except Exception as e:
                errors += 1
                row["status"] = "error"
                row["error"] = str(e)
                per_query.append(row)

        retrieval_recall_at_k = (retrieval_hits / retrieval_used) if retrieval_used else 0.0
        e2e_accuracy = (answer_correct / answer_used) if answer_used else 0.0
        availability = (answer_success / max(len(gold), 1)) if args.run_model else None

        retrieval_failures = (
            cascade_counts["retrieval_fail_answer_ok"] + cascade_counts["retrieval_fail_answer_fail"]
        )
        total_answer_failures = (
            cascade_counts["retrieval_ok_answer_fail"] + cascade_counts["retrieval_fail_answer_fail"]
        )
        cascade_rate_given_retrieval_fail = (
            cascade_counts["retrieval_fail_answer_fail"] / retrieval_failures if retrieval_failures else 0.0
        )
        cascade_share_of_answer_failures = (
            cascade_counts["retrieval_fail_answer_fail"] / total_answer_failures if total_answer_failures else 0.0
        )

        all_results[scenario_id] = {
            "scenario": scenario,
            "summary": {
                "queries_total": len(gold),
                "errors": errors,
                "retrieval_queries_used": retrieval_used,
                "retrieval_hits": retrieval_hits,
                "retrieval_hit_rate": round(retrieval_recall_at_k, 4),
                "answer_queries_used_for_accuracy": answer_used,
                "answers_generated": answer_success,
                "correct_answers": answer_correct,
                "e2e_answer_accuracy": round(e2e_accuracy, 4) if args.run_model else None,
                "e2e_answer_accuracy_percent": round(e2e_accuracy * 100, 2) if args.run_model else None,
                "availability_percent": round(availability * 100, 2) if availability is not None else None,
                "cascade_degradation": {
                    **cascade_counts,
                    "cascade_rate_given_retrieval_fail": round(cascade_rate_given_retrieval_fail, 4),
                    "cascade_share_of_answer_failures": round(cascade_share_of_answer_failures, 4),
                },
            },
            "per_query": per_query,
        }

    baseline_acc = all_results.get("baseline", {}).get("summary", {}).get("e2e_answer_accuracy")
    module_swap_table = []
    for scenario in scenarios:
        sid = scenario["scenario_id"]
        ssum = all_results[sid]["summary"]
        acc = ssum.get("e2e_answer_accuracy")
        delta = None
        if baseline_acc is not None and acc is not None:
            delta = round(acc - baseline_acc, 4)
        module_swap_table.append(
            {
                "scenario_id": sid,
                "swap_module": scenario["swap_module"],
                "retrieve_mode": scenario["retrieve_mode"],
                "k": scenario["k"],
                "prompt_variant": scenario["prompt_variant"],
                "e2e_answer_accuracy": acc,
                "delta_vs_baseline": delta,
                "retrieval_hit_rate": ssum.get("retrieval_hit_rate"),
                "availability_percent": ssum.get("availability_percent"),
            }
        )

    output = {
        "meta": {
            "threshold": args.threshold,
            "run_model": args.run_model,
            "scenarios": [s["scenario_id"] for s in scenarios],
        },
        "module_swap": module_swap_table,
        "scenarios": all_results,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Saved:", args.out)
    print(json.dumps(output["module_swap"], indent=2))


if __name__ == "__main__":
    main()
