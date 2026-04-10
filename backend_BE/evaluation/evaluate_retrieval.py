import argparse
import json
import math
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "evaluation" / "gold_queries.jsonl"
DEFAULT_DOC_MAP = ROOT / "rag_store" / "doc_mapping.pkl"
DEFAULT_OUT = ROOT / "evaluation" / "results" / "retrieval_metrics.json"

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-]{3,}")


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


def canonical_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": doc.get("text", ""),
        "source": doc.get("source", ""),
        "type": doc.get("type", ""),
        "label": doc.get("label", ""),
        "metadata": doc.get("metadata", {}),
    }


def doc_key(doc: dict[str, Any]) -> str:
    return json.dumps(canonical_doc(doc), sort_keys=True, ensure_ascii=False)


def build_doc_index_map(documents: list[dict[str, Any]]):
    key_to_ids: dict[str, list[int]] = defaultdict(list)
    for idx, doc in enumerate(documents):
        key_to_ids[doc_key(doc)].append(idx)
    return key_to_ids


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def build_lexical_index(documents: list[dict[str, Any]], max_tokens_per_doc: int = 400):
    postings: dict[str, list[int]] = defaultdict(list)
    doc_freq: Counter[str] = Counter()

    for idx, doc in enumerate(documents):
        text = str(doc.get("text", ""))
        tokens = tokenize(text)[:max_tokens_per_doc]
        uniq = set(tokens)
        for tok in uniq:
            postings[tok].append(idx)
            doc_freq[tok] += 1

    return postings, doc_freq, len(documents)


def lexical_rank_ids(
    query: str,
    postings,
    doc_freq: Counter[str],
    total_docs: int,
    k: int,
    allowed_doc_ids: Optional[set[int]] = None,
):
    q_tokens = tokenize(query)
    if not q_tokens:
        return []

    scores: dict[int, float] = defaultdict(float)
    q_counts = Counter(q_tokens)

    for tok, tfq in q_counts.items():
        ids = postings.get(tok, [])
        if not ids:
            continue
        idf = math.log((total_docs + 1) / (1 + doc_freq.get(tok, 0))) + 1.0
        w = idf * (1.0 + 0.15 * min(tfq, 3))
        for doc_id in ids:
            if allowed_doc_ids is not None and doc_id not in allowed_doc_ids:
                continue
            scores[doc_id] += w

    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return [doc_id for doc_id, _ in ranked[:k]]


def rrf_fuse(dense_ids: list[int], lexical_ids: list[int], k: int, rrf_k: int = 60):
    rank_dense = {doc_id: rank for rank, doc_id in enumerate(dense_ids, start=1)}
    rank_lex = {doc_id: rank for rank, doc_id in enumerate(lexical_ids, start=1)}
    universe = set(dense_ids) | set(lexical_ids)

    scored = []
    for doc_id in universe:
        s = 0.0
        rd = rank_dense.get(doc_id)
        rl = rank_lex.get(doc_id)
        if rd is not None:
            s += 1.0 / (rrf_k + rd)
        if rl is not None:
            s += 1.0 / (rrf_k + rl)
        scored.append((doc_id, s))

    scored.sort(key=lambda x: (-x[1], x[0]))
    return [doc_id for doc_id, _ in scored[:k]]


def cross_encoder_rerank_ids(
    query: str,
    candidate_ids: list[int],
    documents: list[dict[str, Any]],
    cross_encoder,
    top_k: int,
    cross_top_n: int,
) -> list[int]:
    if not candidate_ids or cross_encoder is None:
        return candidate_ids[:top_k]

    pool = candidate_ids[: max(top_k, cross_top_n)]
    pairs = []
    kept_ids = []
    for doc_id in pool:
        if doc_id < 0 or doc_id >= len(documents):
            continue
        txt = str(documents[doc_id].get("text", ""))[:2500]
        if not txt:
            continue
        pairs.append([query, txt])
        kept_ids.append(doc_id)

    if not pairs:
        return candidate_ids[:top_k]

    try:
        scores = cross_encoder.predict(pairs)
        ranked = sorted(zip(kept_ids, scores), key=lambda x: (-float(x[1]), x[0]))
        reranked = [doc_id for doc_id, _ in ranked]
        return reranked[:top_k]
    except Exception:
        return candidate_ids[:top_k]


def recall_at_k(retrieved_ids: list[int], expected_ids: set[int]) -> float:
    if not expected_ids:
        return 0.0
    hits = len(set(retrieved_ids) & expected_ids)
    return hits / len(expected_ids)


def precision_at_k(retrieved_ids: list[int], expected_ids: set[int], k: int) -> float:
    if k <= 0:
        return 0.0
    hits = len(set(retrieved_ids[:k]) & expected_ids)
    return hits / k


def reciprocal_rank(retrieved_ids: list[int], expected_ids: set[int]) -> float:
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in expected_ids:
            return 1.0 / rank
    return 0.0


def build_query_text(item: dict[str, Any], expand_with_expected_points: bool) -> str:
    query = str(item.get("query", "")).strip()
    if not expand_with_expected_points:
        return query
    points = item.get("expected_points", []) or []
    extra = " ".join(str(p).strip() for p in points if str(p).strip())
    return f"{query} {extra}".strip() if extra else query


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--doc-map", type=Path, default=DEFAULT_DOC_MAP)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-queries", type=int, default=0, help="Evaluate first N queries only (0=all)")

    parser.add_argument("--retrieve-mode", choices=["global", "report_only", "hybrid"], default="global")
    parser.add_argument("--report-id", type=str, default=None, help="Optional default report_id when missing in rows")
    parser.add_argument("--candidate-k", type=int, default=20, help="Dense candidate pool size")
    parser.add_argument("--lexical-k", type=int, default=80, help="Lexical candidate pool size")
    parser.add_argument("--method", choices=["dense", "hybrid_fusion"], default="hybrid_fusion")
    parser.add_argument("--rrf-k", type=int, default=60, help="RRF constant for hybrid_fusion")
    parser.add_argument("--expand-with-expected-points", action="store_true", help="Append expected_points to query text")

    parser.add_argument("--use-cross-encoder", action="store_true", help="Apply cross-encoder rerank over fused candidates")
    parser.add_argument("--cross-encoder-model", type=str, default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--cross-top-n", type=int, default=40, help="Top-N candidates to rerank with cross encoder")

    args = parser.parse_args()

    if not args.gold.exists():
        raise FileNotFoundError(f"Gold file missing: {args.gold}")
    if not args.doc_map.exists():
        raise FileNotFoundError(f"Doc mapping missing: {args.doc_map}")
    if args.candidate_k < args.k:
        raise SystemExit("--candidate-k must be >= --k")
    if args.cross_top_n < args.k:
        raise SystemExit("--cross-top-n must be >= --k")

    import sys
    sys.path.insert(0, str(ROOT))
    from RAG.retreival import retrieve_context  # noqa: E402

    with args.doc_map.open("rb") as f:
        documents = pickle.load(f)

    key_to_ids = build_doc_index_map(documents)
    postings, doc_freq, total_docs = build_lexical_index(documents)

    cross_encoder = None
    if args.use_cross_encoder:
        try:
            from sentence_transformers import CrossEncoder  # noqa: E402

            cross_encoder = CrossEncoder(args.cross_encoder_model)
            print(f"Loaded cross-encoder: {args.cross_encoder_model}")
        except Exception as e:
            print(f"[WARN] cross-encoder unavailable ({e}); continuing without it.")
            cross_encoder = None

    report_to_ids: dict[str, set[int]] = defaultdict(set)
    for idx, d in enumerate(documents):
        meta = d.get("metadata") if isinstance(d, dict) else None
        rid = meta.get("report_id") if isinstance(meta, dict) else None
        if rid:
            report_to_ids[str(rid)].add(idx)

    gold = load_jsonl(args.gold)
    if args.max_queries > 0:
        gold = gold[: args.max_queries]

    per_query = []
    used_queries = 0
    skipped_missing_expected = 0
    skipped_missing_report_id = 0

    for item in gold:
        qid = item.get("id")
        query = str(item.get("query", "")).strip()
        expected_doc_ids = item.get("expected_doc_ids", [])

        if not query:
            per_query.append({"id": qid, "status": "skipped_empty_query"})
            continue

        if not expected_doc_ids:
            skipped_missing_expected += 1
            per_query.append({"id": qid, "query": query, "status": "skipped_missing_expected_doc_ids"})
            continue

        report_id = item.get("report_id") or args.report_id
        if args.retrieve_mode in {"report_only", "hybrid"} and not report_id:
            skipped_missing_report_id += 1
            per_query.append({"id": qid, "query": query, "status": "skipped_missing_report_id"})
            continue

        expected_set = set(int(x) for x in expected_doc_ids)

        dense_docs = retrieve_context(
            query,
            k=args.candidate_k,
            report_id=report_id,
            retrieve_mode=args.retrieve_mode,
        )

        dense_ids = []
        for d in dense_docs:
            candidate_ids = key_to_ids.get(doc_key(d), [])
            if candidate_ids:
                dense_ids.append(candidate_ids[0])

        dense_ids = list(dict.fromkeys(dense_ids))

        if args.method == "dense":
            candidate_ids = dense_ids[: args.candidate_k]
            lexical_ids = []
        else:
            qtext = build_query_text(item, args.expand_with_expected_points)
            allowed_ids = None
            if report_id and args.retrieve_mode in {"report_only", "hybrid"}:
                allowed_ids = report_to_ids.get(str(report_id), set())
            lexical_ids = lexical_rank_ids(
                qtext,
                postings,
                doc_freq,
                total_docs,
                k=args.lexical_k,
                allowed_doc_ids=allowed_ids,
            )
            candidate_ids = rrf_fuse(
                dense_ids,
                lexical_ids,
                k=max(args.k, args.cross_top_n if args.use_cross_encoder else args.k),
                rrf_k=args.rrf_k,
            )

        if args.use_cross_encoder and cross_encoder is not None:
            final_ids = cross_encoder_rerank_ids(
                query=query,
                candidate_ids=candidate_ids,
                documents=documents,
                cross_encoder=cross_encoder,
                top_k=args.k,
                cross_top_n=args.cross_top_n,
            )
        else:
            final_ids = candidate_ids[: args.k]

        r_at_k = recall_at_k(final_ids, expected_set)
        p_at_k = precision_at_k(final_ids, expected_set, args.k)
        rr = reciprocal_rank(final_ids, expected_set)

        used_queries += 1
        per_query.append(
            {
                "id": qid,
                "query": query,
                "expected_doc_ids": sorted(expected_set),
                "retrieved_doc_ids": final_ids,
                "dense_candidate_ids": dense_ids[: args.candidate_k],
                "lexical_candidate_ids": lexical_ids[: args.lexical_k] if args.method == "hybrid_fusion" else [],
                "retrieve_mode": args.retrieve_mode,
                "method": args.method,
                "candidate_k": args.candidate_k,
                "lexical_k": args.lexical_k,
                "rrf_k": args.rrf_k,
                "use_cross_encoder": bool(args.use_cross_encoder and cross_encoder is not None),
                f"recall@{args.k}": round(r_at_k, 4),
                f"precision@{args.k}": round(p_at_k, 4),
                "rr": round(rr, 4),
                "status": "ok",
            }
        )

    if used_queries > 0:
        ok_rows = [q for q in per_query if q.get("status") == "ok"]
        avg_recall = sum(q.get(f"recall@{args.k}", 0.0) for q in ok_rows) / used_queries
        avg_precision = sum(q.get(f"precision@{args.k}", 0.0) for q in ok_rows) / used_queries
        mrr = sum(q.get("rr", 0.0) for q in ok_rows) / used_queries
    else:
        avg_recall = 0.0
        avg_precision = 0.0
        mrr = 0.0

    summary = {
        "k": args.k,
        "retrieve_mode": args.retrieve_mode,
        "method": args.method,
        "candidate_k": args.candidate_k,
        "lexical_k": args.lexical_k,
        "rrf_k": args.rrf_k,
        "use_cross_encoder": bool(args.use_cross_encoder and cross_encoder is not None),
        "cross_encoder_model": args.cross_encoder_model if args.use_cross_encoder else None,
        "cross_top_n": args.cross_top_n if args.use_cross_encoder else None,
        "expand_with_expected_points": args.expand_with_expected_points,
        "queries_total": len(gold),
        "queries_used": used_queries,
        "queries_skipped_missing_expected_doc_ids": skipped_missing_expected,
        "queries_skipped_missing_report_id": skipped_missing_report_id,
        f"avg_recall@{args.k}": round(avg_recall, 4),
        f"avg_precision@{args.k}": round(avg_precision, 4),
        "mrr": round(mrr, 4),
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
