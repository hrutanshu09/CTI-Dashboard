import argparse
import itertools
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVAL = ROOT / "evaluation" / "evaluate_retrieval.py"
DEFAULT_RESULTS = ROOT / "evaluation" / "results"


def run_once(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def load_summary(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("summary", {})


def main():
    parser = argparse.ArgumentParser(description="Tune retrieval evaluation settings and pick best config")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--retrieve-mode", choices=["global", "report_only", "hybrid"], default="global")
    parser.add_argument("--report-id", type=str, default=None)
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--expand-with-expected-points", action="store_true")
    parser.add_argument("--use-cross-encoder", action="store_true")
    parser.add_argument("--cross-encoder-model", type=str, default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--candidate-k-grid", type=str, default="20,30,50")
    parser.add_argument("--lexical-k-grid", type=str, default="80,120,200")
    parser.add_argument("--rrf-k-grid", type=str, default="40,50,60")
    parser.add_argument("--cross-top-n-grid", type=str, default="30,50")
    parser.add_argument("--out", type=Path, default=DEFAULT_RESULTS / "retrieval_tuning_results.json")
    args = parser.parse_args()

    if not args.gold.exists():
        raise FileNotFoundError(f"Gold file missing: {args.gold}")

    candidate_grid = [int(x.strip()) for x in args.candidate_k_grid.split(",") if x.strip()]
    lexical_grid = [int(x.strip()) for x in args.lexical_k_grid.split(",") if x.strip()]
    rrf_grid = [int(x.strip()) for x in args.rrf_k_grid.split(",") if x.strip()]
    cross_top_grid = [int(x.strip()) for x in args.cross_top_n_grid.split(",") if x.strip()]

    experiments = []
    best = None

    for cand_k, lex_k, rrf_k in itertools.product(candidate_grid, lexical_grid, rrf_grid):
        cross_values = cross_top_grid if args.use_cross_encoder else [None]
        for cross_top in cross_values:
            out_path = DEFAULT_RESULTS / f"retrieval_tune_tmp_ck{cand_k}_lk{lex_k}_rrf{rrf_k}_ct{cross_top if cross_top is not None else 0}.json"

            cmd = [
                sys.executable,
                str(DEFAULT_EVAL),
                "--gold", str(args.gold),
                "--k", str(args.k),
                "--retrieve-mode", args.retrieve_mode,
                "--method", "hybrid_fusion",
                "--candidate-k", str(cand_k),
                "--lexical-k", str(lex_k),
                "--rrf-k", str(rrf_k),
                "--out", str(out_path),
            ]
            if args.max_queries > 0:
                cmd += ["--max-queries", str(args.max_queries)]
            if args.report_id:
                cmd += ["--report-id", args.report_id]
            if args.expand_with_expected_points:
                cmd += ["--expand-with-expected-points"]
            if args.use_cross_encoder:
                cmd += [
                    "--use-cross-encoder",
                    "--cross-encoder-model", args.cross_encoder_model,
                    "--cross-top-n", str(cross_top),
                ]

            rc, stdout, stderr = run_once(cmd)
            if rc != 0 or not out_path.exists():
                experiments.append(
                    {
                        "candidate_k": cand_k,
                        "lexical_k": lex_k,
                        "rrf_k": rrf_k,
                        "cross_top_n": cross_top,
                        "status": "error",
                        "error": (stderr or stdout)[-1000:],
                    }
                )
                continue

            s = load_summary(out_path)
            rec = float(s.get(f"avg_recall@{args.k}", 0.0))
            pre = float(s.get(f"avg_precision@{args.k}", 0.0))
            mrr = float(s.get("mrr", 0.0))
            score = (0.6 * rec) + (0.3 * pre) + (0.1 * mrr)

            row = {
                "candidate_k": cand_k,
                "lexical_k": lex_k,
                "rrf_k": rrf_k,
                "cross_top_n": cross_top,
                f"avg_recall@{args.k}": rec,
                f"avg_precision@{args.k}": pre,
                "mrr": mrr,
                "composite": round(score, 6),
                "status": "ok",
                "result_file": str(out_path),
            }
            experiments.append(row)

            if best is None or row["composite"] > best["composite"]:
                best = row

    output = {
        "meta": {
            "gold": str(args.gold),
            "k": args.k,
            "retrieve_mode": args.retrieve_mode,
            "use_cross_encoder": args.use_cross_encoder,
            "cross_encoder_model": args.cross_encoder_model if args.use_cross_encoder else None,
        },
        "best": best,
        "experiments": experiments,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Saved:", args.out)
    print(json.dumps({"best": best, "experiments": len(experiments)}, indent=2))


if __name__ == "__main__":
    main()
