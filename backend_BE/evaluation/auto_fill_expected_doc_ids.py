import argparse
import json
import math
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "evaluation" / "gold_queries.jsonl"
DEFAULT_DOC_MAP = ROOT / "rag_store" / "doc_mapping.pkl"


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-]{3,}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def build_doc_index_map(documents: list[dict[str, Any]]) -> dict[str, list[int]]:
    key_to_ids: dict[str, list[int]] = defaultdict(list)
    for idx, doc in enumerate(documents):
        key_to_ids[doc_key(doc)].append(idx)
    return key_to_ids


def unique_preserve_order(items: list[int]) -> list[int]:
    seen = set()
    out = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


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

    total_docs = len(documents)
    return postings, doc_freq, total_docs


def lexical_retrieve(query: str, k: int, postings, doc_freq: Counter[str], total_docs: int) -> tuple[list[int], dict[int, float]]:
    q_tokens = tokenize(query)
    if not q_tokens:
        return [], {}

    scores: dict[int, float] = defaultdict(float)
    token_counts = Counter(q_tokens)

    for tok, tfq in token_counts.items():
        docs = postings.get(tok, [])
        if not docs:
            continue
        idf = math.log((total_docs + 1) / (1 + doc_freq.get(tok, 0))) + 1.0
        weight = idf * (1.0 + 0.15 * min(tfq, 3))
        for doc_id in docs:
            scores[doc_id] += weight

    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    ranked_ids = [doc_id for doc_id, _ in ranked[: max(k, 20)]]
    score_map = {doc_id: score for doc_id, score in ranked}
    return ranked_ids, score_map


def dense_retrieve_ids(query: str, k: int, retrieve_context, key_to_ids: dict[str, list[int]]) -> list[int]:
    retrieved_docs = retrieve_context(query, k=k)
    predicted_ids: list[int] = []
    for d in retrieved_docs:
        ids = key_to_ids.get(doc_key(d), [])
        if ids:
            predicted_ids.append(ids[0])
    return unique_preserve_order(predicted_ids)[:k]


def merge_ids(a: list[int], b: list[int], k: int, mode: str) -> list[int]:
    if mode == "union":
        mode = "union_interleave"

    if mode == "union_interleave":
        merged: list[int] = []
        max_len = max(len(a), len(b))
        for i in range(max_len):
            if i < len(a):
                merged.append(a[i])
            if i < len(b):
                merged.append(b[i])
        return unique_preserve_order(merged)[:k]

    if mode == "intersection":
        aset = set(a)
        bset = set(b)
        common = [x for x in a if x in bset] + [x for x in b if x in aset]
        return unique_preserve_order(common)[:k]

    if mode == "dense_first":
        return unique_preserve_order(b + a)[:k]

    return a[:k]


def build_query_text(row: dict[str, Any]) -> str:
    query = str(row.get("query", "")).strip()
    expected_points = row.get("expected_points", []) or []
    extras = " ".join(str(p).strip() for p in expected_points if str(p).strip())
    if extras:
        return f"{query} {extras}"
    return query


def rerank_diverse(
    candidate_ids: list[int],
    documents: list[dict[str, Any]],
    k: int,
    max_per_source: int,
    max_per_type: int,
) -> list[int]:
    if not candidate_ids:
        return []

    source_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    selected: list[int] = []

    for doc_id in candidate_ids:
        if doc_id < 0 or doc_id >= len(documents):
            continue

        doc = documents[doc_id]
        src = str(doc.get("source", "unknown") or "unknown")
        typ = str(doc.get("type", "unknown") or "unknown")

        if source_counts[src] >= max_per_source:
            continue
        if type_counts[typ] >= max_per_type:
            continue

        selected.append(doc_id)
        source_counts[src] += 1
        type_counts[typ] += 1
        if len(selected) >= k:
            break

    if len(selected) < k:
        for doc_id in candidate_ids:
            if doc_id in selected:
                continue
            selected.append(doc_id)
            if len(selected) >= k:
                break

    return unique_preserve_order(selected)[:k]


def safe_norm(vals: dict[int, float]) -> dict[int, float]:
    if not vals:
        return {}
    vmin = min(vals.values())
    vmax = max(vals.values())
    if vmax <= vmin:
        return {k: 0.0 for k in vals}
    return {k: (v - vmin) / (vmax - vmin) for k, v in vals.items()}


def teacher_rerank_ids(
    query: str,
    query_text: str,
    documents: list[dict[str, Any]],
    k: int,
    lexical_ids: list[int],
    lexical_scores: dict[int, float],
    dense_ids: list[int],
    cross_encoder=None,
    cross_encoder_weight: float = 0.55,
    lexical_weight: float = 0.30,
    dense_weight: float = 0.15,
) -> list[int]:
    candidates = unique_preserve_order(lexical_ids + dense_ids)
    if not candidates:
        return []

    lex_norm = safe_norm({cid: lexical_scores.get(cid, 0.0) for cid in candidates})
    dense_rank_score: dict[int, float] = {}
    for r, cid in enumerate(dense_ids, start=1):
        dense_rank_score[cid] = 1.0 / r

    ce_scores: dict[int, float] = {}
    if cross_encoder is not None:
        pairs = []
        pair_ids = []
        # Keep CE cost bounded.
        pool = candidates[: max(40, min(120, len(candidates)))]
        for cid in pool:
            text = str(documents[cid].get("text", ""))[:2000]
            pairs.append([query, text])
            pair_ids.append(cid)
        try:
            raw_scores = cross_encoder.predict(pairs)
            for cid, s in zip(pair_ids, raw_scores):
                ce_scores[cid] = float(s)
        except Exception:
            ce_scores = {}

    ce_norm = safe_norm(ce_scores)

    blended: list[tuple[int, float]] = []
    for cid in candidates:
        score = 0.0
        score += lexical_weight * lex_norm.get(cid, 0.0)
        score += dense_weight * dense_rank_score.get(cid, 0.0)
        if ce_norm:
            score += cross_encoder_weight * ce_norm.get(cid, 0.0)
        # Mild token overlap bias for robustness.
        q_tokens = set(tokenize(query_text))
        d_tokens = set(tokenize(str(documents[cid].get("text", ""))[:2500]))
        overlap = (len(q_tokens & d_tokens) / max(1, len(q_tokens)))
        score += 0.05 * overlap
        blended.append((cid, score))

    blended.sort(key=lambda x: (-x[1], x[0]))
    ranked = [cid for cid, _ in blended]
    return ranked[:k]


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-fill expected_doc_ids in gold_queries.jsonl")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--doc-map", type=Path, default=DEFAULT_DOC_MAP)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite non-empty expected_doc_ids")
    parser.add_argument("--backup", action="store_true", help="Create .bak backup before writing")
    parser.add_argument(
        "--strategy",
        choices=["dense", "lexical", "union", "intersection", "realistic", "teacher_rerank"],
        default="teacher_rerank",
        help=(
            "Labeling strategy. 'teacher_rerank' builds higher-quality weak labels via hybrid candidates "
            "and optional cross-encoder reranking."
        ),
    )
    parser.add_argument(
        "--max-tokens-per-doc",
        type=int,
        default=400,
        help="Max tokens per document used for lexical index.",
    )
    parser.add_argument("--max-per-source", type=int, default=2, help="Diversity cap per source for realistic strategy")
    parser.add_argument("--max-per-type", type=int, default=2, help="Diversity cap per type for realistic strategy")
    parser.add_argument("--candidate-k-lexical", type=int, default=60, help="Lexical candidate pool for teacher_rerank")
    parser.add_argument("--candidate-k-dense", type=int, default=40, help="Dense candidate pool for teacher_rerank")
    parser.add_argument("--teacher-model", type=str, default="cross-encoder/ms-marco-MiniLM-L-6-v2", help="Cross-encoder model")
    parser.add_argument("--disable-cross-encoder", action="store_true", help="Skip cross-encoder and use hybrid blended rerank only")
    args = parser.parse_args()

    if not args.gold.exists():
        raise FileNotFoundError(f"Gold file missing: {args.gold}")
    if not args.doc_map.exists():
        raise FileNotFoundError(f"Doc mapping missing: {args.doc_map}")

    with args.doc_map.open("rb") as f:
        documents = pickle.load(f)

    rows = load_jsonl(args.gold)

    need_dense = args.strategy in {"dense", "union", "intersection", "teacher_rerank"}
    retrieve_context = None
    key_to_ids: dict[str, list[int]] = {}
    if need_dense:
        import sys
        sys.path.insert(0, str(ROOT))
        from RAG.retreival import retrieve_context as _retrieve_context  # noqa: E402

        retrieve_context = _retrieve_context
        key_to_ids = build_doc_index_map(documents)

    need_lex = args.strategy in {"lexical", "union", "intersection", "realistic", "teacher_rerank"}
    postings = None
    doc_freq = None
    total_docs = len(documents)
    if need_lex:
        postings, doc_freq, total_docs = build_lexical_index(
            documents,
            max_tokens_per_doc=max(20, args.max_tokens_per_doc),
        )

    cross_encoder = None
    if args.strategy == "teacher_rerank" and not args.disable_cross_encoder:
        try:
            from sentence_transformers import CrossEncoder  # noqa: E402

            cross_encoder = CrossEncoder(args.teacher_model)
            print(f"Loaded teacher reranker: {args.teacher_model}")
        except Exception as e:
            print(f"[WARN] Could not load cross-encoder ({e}); continuing without it.")
            cross_encoder = None

    updated = 0
    skipped_existing = 0
    skipped_empty_query = 0

    for row in rows:
        query = str(row.get("query", "")).strip()
        existing = row.get("expected_doc_ids", []) or []

        if not query:
            skipped_empty_query += 1
            continue

        if existing and not args.overwrite:
            skipped_existing += 1
            continue

        dense_ids: list[int] = []
        lexical_ids: list[int] = []
        lexical_scores: dict[int, float] = {}

        query_text = build_query_text(row)

        if args.strategy in {"dense", "union", "intersection"}:
            dense_ids = dense_retrieve_ids(query, args.k, retrieve_context, key_to_ids)

        if args.strategy in {"lexical", "union", "intersection", "realistic"}:
            lexical_ids, lexical_scores = lexical_retrieve(query_text, args.k, postings, doc_freq, total_docs)

        if args.strategy == "teacher_rerank":
            lexical_ids, lexical_scores = lexical_retrieve(
                query_text,
                max(args.candidate_k_lexical, args.k),
                postings,
                doc_freq,
                total_docs,
            )
            dense_ids = dense_retrieve_ids(
                query,
                max(args.candidate_k_dense, args.k),
                retrieve_context,
                key_to_ids,
            )

        if args.strategy == "dense":
            expected_ids = dense_ids
        elif args.strategy == "lexical":
            expected_ids = lexical_ids[: args.k]
        elif args.strategy == "union":
            expected_ids = merge_ids(lexical_ids, dense_ids, args.k, "union")
        elif args.strategy == "intersection":
            expected_ids = merge_ids(lexical_ids, dense_ids, args.k, "intersection")
        elif args.strategy == "realistic":
            expected_ids = rerank_diverse(
                lexical_ids,
                documents,
                k=args.k,
                max_per_source=max(1, args.max_per_source),
                max_per_type=max(1, args.max_per_type),
            )
        else:
            expected_ids = teacher_rerank_ids(
                query=query,
                query_text=query_text,
                documents=documents,
                k=args.k,
                lexical_ids=lexical_ids,
                lexical_scores=lexical_scores,
                dense_ids=dense_ids,
                cross_encoder=cross_encoder,
            )

        row["expected_doc_ids"] = unique_preserve_order(expected_ids)[: args.k]
        row["expected_doc_ids_strategy"] = args.strategy
        updated += 1

    if args.backup:
        backup_path = args.gold.with_suffix(args.gold.suffix + ".bak")
        backup_path.write_text(args.gold.read_text(encoding="utf-8"), encoding="utf-8")

    write_jsonl(args.gold, rows)

    print(f"Strategy: {args.strategy}")
    print(f"Updated rows: {updated}")
    print(f"Skipped (already had expected_doc_ids): {skipped_existing}")
    print(f"Skipped (empty query): {skipped_empty_query}")
    print(f"Saved: {args.gold}")


if __name__ == "__main__":
    main()
