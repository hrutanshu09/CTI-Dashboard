# RAG Evaluation Setup

This folder contains scripts and data to validate RAG retrieval and answer quality.

## Files

- `gold_queries.jsonl`: Gold benchmark cases.
- `gold_queries_core.jsonl`: Core benchmark split.
- `gold_queries_stress.jsonl`: Stress benchmark split.
- `inspect_doc_mapping.py`: Find doc IDs from `rag_store/doc_mapping.pkl`.
- `auto_fill_expected_doc_ids.py`: Fill pseudo labels for `expected_doc_ids`.
- `build_benchmark_splits.py`: Build core/stress splits from gold queries.
- `evaluate_retrieval.py`: Computes Recall@K, Precision@K, and MRR with dense/hybrid options.
- `tune_retrieval_configs.py`: Grid-search retrieval params and select best config.
- `evaluate_generation.py`: Builds generation evaluation output (template or actual model run).
- `evaluate_answer_accuracy.py`: Computes strict answer accuracy from expected points.
- `evaluate_modular_rag.py`: Computes module swap impact, cascade degradation, and E2E answer accuracy.
- `build_report.py`: Merges outputs into one markdown report.
- `results/`: Generated JSON/Markdown outputs.

## Gold Query Schema

Each line in `gold_queries.jsonl` is one JSON object:

```json
{
  "id": "q001",
  "query": "Suspicious repeated failed logins from same source IP",
  "expected_doc_ids": [12, 89],
  "expected_points": [
    "Brute force behavior",
    "Monitor authentication logs",
    "Block or rate-limit suspicious source IP"
  ]
}
```

Notes:
- `expected_doc_ids` must be integer indexes from `doc_mapping.pkl`.
- `expected_points` should be 2-5 short expected facts.
- Optional `report_id` can be added for report-scoped retrieval evaluation.

## Commands

Run from project root (`CTI-Dashboard`):

```powershell
python backend_BE/evaluation/build_benchmark_splits.py
```

```powershell
python backend_BE/evaluation/evaluate_retrieval.py --gold backend_BE/evaluation/gold_queries_core.jsonl --k 5 --method hybrid_fusion --candidate-k 30 --lexical-k 120 --rrf-k 50 --expand-with-expected-points --out backend_BE/evaluation/results/retrieval_metrics_core.json
python backend_BE/evaluation/evaluate_retrieval.py --gold backend_BE/evaluation/gold_queries_stress.jsonl --k 5 --method hybrid_fusion --candidate-k 30 --lexical-k 120 --rrf-k 50 --expand-with-expected-points --out backend_BE/evaluation/results/retrieval_metrics_stress.json
```

Optional cross-encoder reranking:

```powershell
python backend_BE/evaluation/evaluate_retrieval.py --gold backend_BE/evaluation/gold_queries_core.jsonl --k 5 --method hybrid_fusion --candidate-k 30 --lexical-k 120 --rrf-k 50 --expand-with-expected-points --use-cross-encoder --cross-top-n 40
```

Automatic tuning sweep (quick):

```powershell
python backend_BE/evaluation/tune_retrieval_configs.py --gold backend_BE/evaluation/gold_queries_core.jsonl --k 5 --expand-with-expected-points --max-queries 20 --candidate-k-grid "20,30" --lexical-k-grid "80,120" --rrf-k-grid "40,60" --out backend_BE/evaluation/results/retrieval_tuning_results_quick.json
```

Generation/accuracy:

```powershell
python backend_BE/evaluation/evaluate_answer_accuracy.py --threshold 0.67
python backend_BE/evaluation/evaluate_modular_rag.py --run-model --scenarios "baseline,swap_retrieval_k5,swap_retrieval_k15,swap_prompt_concise"
```
