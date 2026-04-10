"""
Bulk ingest threat report files (.pdf/.txt/.log/.csv) into the global RAG store.

Usage (from project root):
  python backend_BE/RAG/ingest_threat_reports.py --input-dir "D:\\reports"
  python backend_BE/RAG/ingest_threat_reports.py --input-dir "D:\\reports" --recursive
  python backend_BE/RAG/ingest_threat_reports.py --input-dir "D:\\reports" --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time
from pathlib import Path
import sys
from typing import Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.report_processing import (  # noqa: E402
    chunk_report,
    ingest_report_into_global_kb,
    normalize_report,
)


SUPPORTED_EXTS = {"pdf", "txt", "log", "csv"}


def extract_pdf_text(raw_bytes: bytes) -> str:
    import fitz  # PyMuPDF

    with fitz.open(stream=raw_bytes, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def should_take(index_1based: int, sample_rate: float) -> bool:
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    stride = max(1, int(round(1.0 / sample_rate)))
    return (index_1based - 1) % stride == 0


def csv_to_text(
    text: str,
    max_rows: int,
    sample_rate: float,
    fast_log_mode: bool,
) -> str:
    """
    Convert CSV rows into line-oriented natural text for semantic retrieval.
    """
    reader = csv.DictReader(text.splitlines())
    selected: List[str] = []
    seen_rows = 0

    for row in reader:
        seen_rows += 1
        if max_rows > 0 and seen_rows > max_rows:
            break
        if not should_take(seen_rows, sample_rate):
            continue

        if fast_log_mode:
            # Keep fewer, denser records in fast mode.
            if len(selected) >= 5000:
                break

        pairs = []
        for key, value in row.items():
            key_norm = str(key or "").strip()
            val_norm = str(value or "").strip()
            if not key_norm or not val_norm:
                continue
            pairs.append(f"{key_norm}: {val_norm}")

        if pairs:
            selected.append(f"Row {seen_rows}: " + " | ".join(pairs))

    if fast_log_mode:
        header = [
            f"CSV summary: rows_seen={seen_rows}",
            f"rows_selected={len(selected)}",
            "mode=fast_log_mode",
        ]
        return "\n".join(header + selected)

    return "\n".join(selected) if selected else text


def textlog_to_text(
    text: str,
    max_rows: int,
    sample_rate: float,
    fast_log_mode: bool,
) -> str:
    lines = text.splitlines()
    selected: List[str] = []

    for idx, line in enumerate(lines, start=1):
        if max_rows > 0 and idx > max_rows:
            break
        if not should_take(idx, sample_rate):
            continue
        line = line.strip()
        if not line:
            continue

        if fast_log_mode and len(selected) >= 10000:
            break

        selected.append(line)

    if fast_log_mode:
        header = [
            f"Text/log summary: lines_seen={len(lines)}",
            f"lines_selected={len(selected)}",
            "mode=fast_log_mode",
        ]
        return "\n".join(header + selected)

    return "\n".join(selected) if selected else text


def read_file_text(
    path: Path,
    max_rows: int,
    sample_rate: float,
    fast_log_mode: bool,
) -> tuple[bytes, str]:
    raw = path.read_bytes()
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        text = extract_pdf_text(raw)
    elif suffix == ".csv":
        decoded = raw.decode("utf-8", errors="ignore")
        text = csv_to_text(decoded, max_rows=max_rows, sample_rate=sample_rate, fast_log_mode=fast_log_mode)
    else:
        decoded = raw.decode("utf-8", errors="ignore")
        text = textlog_to_text(decoded, max_rows=max_rows, sample_rate=sample_rate, fast_log_mode=fast_log_mode)

    return raw, text


def iter_files(input_dir: Path, recursive: bool, include_exts: Sequence[str]) -> Iterable[Path]:
    patterns = [f"*.{ext}" for ext in include_exts]
    for pattern in patterns:
        if recursive:
            yield from input_dir.rglob(pattern)
        else:
            yield from input_dir.glob(pattern)


def parse_exts(raw: str) -> List[str]:
    if not raw.strip():
        return sorted(SUPPORTED_EXTS)

    parsed = []
    for part in raw.split(","):
        ext = part.strip().lower().lstrip(".")
        if not ext:
            continue
        if ext not in SUPPORTED_EXTS:
            raise ValueError(f"Unsupported extension '{ext}'. Supported: {sorted(SUPPORTED_EXTS)}")
        parsed.append(ext)

    if not parsed:
        return sorted(SUPPORTED_EXTS)
    return sorted(set(parsed))


def stable_sample_key(path: Path) -> str:
    return hashlib.md5(str(path).encode("utf-8", errors="ignore")).hexdigest()[:8]


def main():
    parser = argparse.ArgumentParser(description="Bulk ingest threat report files into RAG")
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing report files")
    parser.add_argument("--recursive", action="store_true", help="Scan subdirectories recursively")
    parser.add_argument("--dry-run", action="store_true", help="Parse/chunk only; do not write to index")

    parser.add_argument("--include-ext", type=str, default="pdf,txt,log,csv", help="Comma-separated ext list")
    parser.add_argument("--max-files", type=int, default=0, help="Process at most N files (0=no limit)")
    parser.add_argument("--max-rows", type=int, default=0, help="Use at most N rows/lines for csv/txt/log (0=no limit)")
    parser.add_argument("--sample-rate", type=float, default=1.0, help="Keep approximately this fraction of rows/lines (0-1]")
    parser.add_argument("--max-chunks-per-file", type=int, default=0, help="Cap chunks per file after chunking (0=no limit)")
    parser.add_argument("--chunk-size", type=int, default=1500, help="Chunk size passed to chunk_report")
    parser.add_argument("--overlap", type=int, default=200, help="Chunk overlap passed to chunk_report")
    parser.add_argument("--fast-log-mode", action="store_true", help="Aggressive compaction for large csv/log/txt")

    args = parser.parse_args()

    if args.sample_rate <= 0 or args.sample_rate > 1:
        raise SystemExit("--sample-rate must be in (0, 1].")
    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be > 0.")
    if args.overlap < 0:
        raise SystemExit("--overlap must be >= 0.")

    input_dir = args.input_dir
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Invalid input directory: {input_dir}")

    include_exts = parse_exts(args.include_ext)

    files = sorted({p.resolve() for p in iter_files(input_dir, args.recursive, include_exts) if p.is_file()})
    if args.max_files > 0:
        files = files[: args.max_files]

    if not files:
        print(f"No supported files found for extensions: {include_exts}")
        return

    total_files = 0
    total_chunks = 0
    total_new_chunks = 0
    already_ingested = 0
    failed = 0

    print(f"Found {len(files)} file(s) to process.")
    print(
        f"Options: ext={include_exts} | max_rows={args.max_rows} | sample_rate={args.sample_rate} | "
        f"max_chunks_per_file={args.max_chunks_per_file} | chunk_size={args.chunk_size} | overlap={args.overlap} | "
        f"fast_log_mode={args.fast_log_mode}"
    )

    run_start = time.time()

    for i, path in enumerate(files, start=1):
        total_files += 1
        file_start = time.time()
        try:
            raw, text = read_file_text(
                path,
                max_rows=args.max_rows,
                sample_rate=args.sample_rate,
                fast_log_mode=args.fast_log_mode,
            )
            normalized = normalize_report(text)
            chunks = chunk_report(normalized, chunk_size=args.chunk_size, overlap=args.overlap)

            if args.max_chunks_per_file > 0 and len(chunks) > args.max_chunks_per_file:
                chunks = chunks[: args.max_chunks_per_file]

            total_chunks += len(chunks)

            elapsed = time.time() - file_start
            avg_so_far = (time.time() - run_start) / i
            remaining = max(0, len(files) - i)
            eta_sec = int(avg_so_far * remaining)

            if args.dry_run:
                print(
                    f"[DRY-RUN] {path.name}: chunks={len(chunks)} | t={elapsed:.1f}s | "
                    f"eta~{eta_sec}s | file_key={stable_sample_key(path)}"
                )
                continue

            ingest = ingest_report_into_global_kb(
                raw_bytes=raw,
                filename=path.name,
                chunks=chunks,
            )

            if ingest.get("already_ingested"):
                already_ingested += 1

            total_new_chunks += int(ingest.get("new_chunks_added", 0))

            print(
                f"[OK] {path.name} | report_id={ingest.get('report_id')} | "
                f"chunks={len(chunks)} | new={ingest.get('new_chunks_added', 0)} | "
                f"already_ingested={ingest.get('already_ingested', False)} | "
                f"t={elapsed:.1f}s | eta~{eta_sec}s"
            )
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {path.name}: {exc}")

    print("\nSummary")
    print(f"- Files processed: {total_files}")
    print(f"- Total parsed chunks: {total_chunks}")
    if not args.dry_run:
        print(f"- Newly added chunks: {total_new_chunks}")
        print(f"- Already ingested files: {already_ingested}")
    print(f"- Failed files: {failed}")


if __name__ == "__main__":
    main()
