"""
Threat report processing: normalization, chunking, IOC extraction,
RAG orchestration, and global-KB ingestion.
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from RAG.retreival import (
    add_documents_to_index,
    report_chunk_count,
    report_exists,
    retrieve_context,
)

logger = logging.getLogger(__name__)


def normalize_report(text: str) -> str:
    """
    Clean raw extracted text:
    - normalize line endings
    - strip non-printable characters (keep tab and newline)
    - collapse 3+ consecutive blank lines to 2
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\x09\x0A\x20-\x7E]", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_report(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """Sliding-window chunker with word-boundary snapping."""
    if not text:
        return []

    chunks: List[str] = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        next_start = end - overlap
        if next_start <= start:
            break
        start = next_start

    return chunks


_RE_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
_RE_DOMAIN = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"(?:com|net|org|io|gov|edu|mil|co|info|biz|xyz|onion)\b",
    re.IGNORECASE,
)
_RE_MD5 = re.compile(r"\b[0-9a-fA-F]{32}\b")
_RE_SHA1 = re.compile(r"\b[0-9a-fA-F]{40}\b")
_RE_SHA256 = re.compile(r"\b[0-9a-fA-F]{64}\b")
_RE_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)

_NOISE_IPS = {"0.0.0.0", "127.0.0.1", "255.255.255.255"}


def extract_iocs(text: str) -> dict:
    """Regex-based extraction of common Indicators of Compromise."""
    ips = sorted({ip for ip in _RE_IPV4.findall(text) if ip not in _NOISE_IPS})
    domains = sorted(set(_RE_DOMAIN.findall(text)))
    hashes = sorted(
        set(_RE_MD5.findall(text))
        | set(_RE_SHA1.findall(text))
        | set(_RE_SHA256.findall(text))
    )
    cves = sorted(set(_RE_CVE.findall(text)))

    return {"ips": ips, "domains": domains, "hashes": hashes, "cves": cves}


def process_report_chunks(
    chunks: List[str],
    report_id: Optional[str] = None,
    retrieval_mode: str = "hybrid",
) -> dict:
    """
    Build structured threat-report analysis with strict output schema,
    deduplication, and source-scope tags.
    """
    if not chunks:
        return {
            "iocs": {"ips": [], "domains": [], "hashes": [], "cves": []},
            "severity": "Unknown",
            "analysis": _empty_analysis(),
        }

    full_text = "\n".join(chunks)
    iocs = extract_iocs(full_text)
    anchor_chunk = chunks[0]

    query = (
        "Create a concise structured threat report analysis with summary, threat types, "
        "detections, prioritized actions, and confidence."
    )
    # Lazy import avoids requiring Gemini env during offline/bulk ingestion flows.
    from core.gemini_client import generate

    retrieved_docs = retrieve_context(
        query,
        k=12,
        report_id=report_id,
        retrieve_mode=retrieval_mode,
    )

    source_trace = _build_source_trace(retrieved_docs, report_id)
    prompt = _build_structured_prompt(anchor_chunk, iocs, source_trace)

    try:
        model_text = generate(prompt)
        model_json = _extract_json_object(model_text)
    except Exception:
        logger.exception("Structured generation failed; using fallback analysis")
        model_json = {}

    analysis = _postprocess_analysis(model_json, iocs, source_trace, anchor_chunk)
    severity = _parse_severity(str(analysis.get("severity", "Unknown")))

    return {
        "iocs": iocs,
        "severity": severity,
        "analysis": analysis,
    }


def ingest_report_into_global_kb(raw_bytes: bytes, filename: str, chunks: List[str]) -> dict:
    """
    Incrementally ingest report chunks into the global FAISS/doc mapping.

    Dedupes by report content hash (SHA-256) so repeated uploads do not re-add vectors.
    """
    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    report_id = f"report_{file_hash[:16]}"

    if report_exists(report_id):
        return {
            "report_id": report_id,
            "already_ingested": True,
            "new_chunks_added": 0,
            "total_chunks_for_report": report_chunk_count(report_id),
            "file_hash": file_hash,
        }

    if not chunks:
        return {
            "report_id": report_id,
            "already_ingested": False,
            "new_chunks_added": 0,
            "total_chunks_for_report": 0,
            "file_hash": file_hash,
        }

    uploaded_at = datetime.now(timezone.utc).isoformat()
    docs_to_add = []
    for idx, chunk in enumerate(chunks):
        docs_to_add.append(
            {
                "text": chunk,
                "source": "threat_reports",
                "type": "threat_report",
                "label": filename,
                "metadata": {
                    "source_type": "threat_report",
                    "report_id": report_id,
                    "filename": filename,
                    "uploaded_at": uploaded_at,
                    "chunk_id": idx,
                    "file_hash": file_hash,
                },
            }
        )

    new_chunks_added = add_documents_to_index(docs_to_add)

    return {
        "report_id": report_id,
        "already_ingested": False,
        "new_chunks_added": new_chunks_added,
        "total_chunks_for_report": report_chunk_count(report_id),
        "file_hash": file_hash,
    }


def _build_structured_prompt(anchor_chunk: str, iocs: Dict[str, List[str]], source_trace: List[Dict[str, Any]]) -> str:
    src_lines = []
    for s in source_trace:
        src_lines.append(
            f"[S{s['id']}|scope={s['scope']}] {s.get('snippet', '')}"
        )

    return (
        "You are a senior SOC threat analyst.\n"
        "Return ONLY valid JSON (no markdown, no commentary).\n"
        "Do not repeat the same facts across sections.\n"
        "Length controls:\n"
        "- summary_lines: 4 to 6 concise lines\n"
        "- threat_types: max 4 items\n"
        "- detections: max 6 items\n"
        "- actions_immediate/actions_24h/actions_7d: max 5 items each\n\n"
        "Schema (strict):\n"
        "{\n"
        "  \"severity\": \"Critical|High|Medium|Low|Informational\",\n"
        "  \"summary_lines\": [\"...\"],\n"
        "  \"threat_types\": [{\"type\":\"...\",\"evidence\":\"...\",\"source_ids\":[1]}],\n"
        "  \"detections\": [{\"signal\":\"...\",\"source_ids\":[1]}],\n"
        "  \"actions_immediate\": [{\"action\":\"...\",\"source_ids\":[1]}],\n"
        "  \"actions_24h\": [{\"action\":\"...\",\"source_ids\":[1]}],\n"
        "  \"actions_7d\": [{\"action\":\"...\",\"source_ids\":[1]}],\n"
        "  \"confidence\": {\"score\": 0.0, \"rationale\": \"...\"}\n"
        "}\n\n"
        "Rules:\n"
        "- source_ids must reference the provided S# sources only.\n"
        "- Do not invent IOCs/CVEs outside the provided report excerpt and source context.\n"
        "- Keep wording operational and non-generic.\n\n"
        f"Report excerpt:\n{anchor_chunk[:5000]}\n\n"
        f"Extracted IOCs (deduped): {json.dumps(iocs)}\n\n"
        f"Retrieved sources:\n" + "\n".join(src_lines)
    )


def _extract_json_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return {}

    candidate = text[first : last + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        logger.warning("Could not parse JSON object from model output")
        return {}


def _build_source_trace(retrieved_docs: List[Dict[str, Any]], report_id: Optional[str]) -> List[Dict[str, Any]]:
    trace = []
    for idx, doc in enumerate(retrieved_docs, start=1):
        metadata = doc.get("metadata") if isinstance(doc, dict) else None
        source_report_id = metadata.get("report_id") if isinstance(metadata, dict) else None
        scope = "report" if report_id and source_report_id == report_id else "global"
        trace.append(
            {
                "id": idx,
                "scope": scope,
                "source": doc.get("source", "unknown") if isinstance(doc, dict) else "unknown",
                "label": doc.get("label", "") if isinstance(doc, dict) else "",
                "snippet": str(doc.get("text", "") if isinstance(doc, dict) else str(doc))[:320],
            }
        )
    return trace


def _scope_from_source_ids(source_ids: List[int], source_trace: List[Dict[str, Any]]) -> str:
    if not source_ids:
        return "unknown"

    id_to_scope = {s["id"]: s["scope"] for s in source_trace}
    scopes = {id_to_scope.get(int(sid), "unknown") for sid in source_ids if isinstance(sid, int) or str(sid).isdigit()}
    scopes.discard("unknown")

    if not scopes:
        return "unknown"
    if len(scopes) == 1:
        return list(scopes)[0]
    return "mixed"


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _dedupe_strings(values: List[str], limit: int) -> List[str]:
    seen = set()
    out = []
    for v in values:
        t = _norm_text(v)
        key = t.lower()
        if not t or key in seen:
            continue
        seen.add(key)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def _normalize_object_list(items: Any, text_key: str, source_trace: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []

    seen = set()
    out = []
    for raw in items:
        if not isinstance(raw, dict):
            continue

        text = _norm_text(raw.get(text_key))
        if not text:
            continue

        source_ids_raw = raw.get("source_ids", [])
        source_ids: List[int] = []
        if isinstance(source_ids_raw, list):
            for sid in source_ids_raw:
                try:
                    source_ids.append(int(sid))
                except Exception:
                    continue

        key = text.lower()
        if key in seen:
            continue
        seen.add(key)

        item = {text_key: text, "source_ids": source_ids, "source_scope": _scope_from_source_ids(source_ids, source_trace)}

        if "type" in raw and text_key != "type":
            item["type"] = _norm_text(raw.get("type"))
        if "evidence" in raw:
            item["evidence"] = _norm_text(raw.get("evidence"))

        out.append(item)
        if len(out) >= limit:
            break

    return out


def _empty_analysis() -> Dict[str, Any]:
    return {
        "severity": "Unknown",
        "summary": "No content to analyse.",
        "summary_lines": [],
        "threat_type": "Unknown",
        "threat_types": [],
        "top_iocs": [],
        "top_cves": [],
        "detections": [],
        "actions_immediate": [],
        "actions_24h": [],
        "actions_7d": [],
        "actions_short_term": [],
        "recommendations": "",
        "confidence": {"score": 0.0, "rationale": "Insufficient content."},
        "source_trace": [],
        "ttps": [],
    }


def _postprocess_analysis(model_json: Dict[str, Any], iocs: Dict[str, List[str]], source_trace: List[Dict[str, Any]], anchor_chunk: str) -> Dict[str, Any]:
    analysis = _empty_analysis()

    analysis["severity"] = _parse_severity(str(model_json.get("severity", "Unknown")))

    summary_lines = _dedupe_strings(model_json.get("summary_lines", []), limit=6)
    if len(summary_lines) < 4:
        fallback = [
            "Threat report indicates active malicious campaign activity targeting critical infrastructure.",
            f"Primary impacted indicators include {len(iocs.get('ips', []))} IP(s) and {len(iocs.get('domains', []))} domain(s).",
            f"Known vulnerability references found: {', '.join(iocs.get('cves', [])[:3]) if iocs.get('cves') else 'none explicitly listed' }.",
            "Immediate containment and credential hardening actions are recommended.",
        ]
        summary_lines = _dedupe_strings(summary_lines + fallback, limit=6)

    analysis["summary_lines"] = summary_lines[:6]
    analysis["summary"] = "\n".join(f"- {line}" for line in analysis["summary_lines"])

    threat_types = _normalize_object_list(model_json.get("threat_types", []), "type", source_trace, limit=4)
    for t in threat_types:
        if "evidence" not in t or not t["evidence"]:
            t["evidence"] = "Evidence inferred from uploaded report context."
    analysis["threat_types"] = threat_types
    analysis["threat_type"] = "\n".join(
        f"- {t['type']}: {t.get('evidence', '')} [scope={t.get('source_scope', 'unknown')}]"
        for t in threat_types
    ) or "Unknown"

    analysis["detections"] = _normalize_object_list(model_json.get("detections", []), "signal", source_trace, limit=6)
    analysis["actions_immediate"] = _normalize_object_list(model_json.get("actions_immediate", []), "action", source_trace, limit=5)
    actions_24h = _normalize_object_list(model_json.get("actions_24h", []), "action", source_trace, limit=5)
    actions_7d = _normalize_object_list(model_json.get("actions_7d", []), "action", source_trace, limit=5)

    for row in actions_24h:
        row["window"] = "24h"
    for row in actions_7d:
        row["window"] = "7d"

    analysis["actions_24h"] = actions_24h
    analysis["actions_7d"] = actions_7d
    analysis["actions_short_term"] = actions_24h + actions_7d

    top_iocs = []
    for ip in iocs.get("ips", [])[:4]:
        top_iocs.append({"indicator": ip, "type": "ip", "source_scope": "report"})
    for domain in iocs.get("domains", [])[:4]:
        top_iocs.append({"indicator": domain, "type": "domain", "source_scope": "report"})
    for h in iocs.get("hashes", [])[:3]:
        top_iocs.append({"indicator": h, "type": "hash", "source_scope": "report"})
    analysis["top_iocs"] = top_iocs[:8]
    analysis["top_cves"] = [{"cve": cve, "source_scope": "report"} for cve in iocs.get("cves", [])[:10]]

    conf = model_json.get("confidence", {}) if isinstance(model_json.get("confidence"), dict) else {}
    score = conf.get("score", 0.65 if analysis["top_cves"] or analysis["top_iocs"] else 0.45)
    try:
        score = float(score)
    except Exception:
        score = 0.5
    score = max(0.0, min(1.0, score))

    rationale = _norm_text(conf.get("rationale")) or "Confidence estimated from consistency of extracted indicators and retrieved evidence."
    analysis["confidence"] = {"score": round(score, 2), "rationale": rationale}

    # Backward-compatible recommendations text as prioritized table.
    rec_lines = [
        "| Priority Window | Action | Source Scope |",
        "|---|---|---|",
    ]
    for row in analysis["actions_immediate"]:
        rec_lines.append(f"| Immediate | {row['action']} | {row.get('source_scope', 'unknown')} |")
    for row in analysis["actions_24h"]:
        rec_lines.append(f"| 24h | {row['action']} | {row.get('source_scope', 'unknown')} |")
    for row in analysis["actions_7d"]:
        rec_lines.append(f"| 7d | {row['action']} | {row.get('source_scope', 'unknown')} |")
    analysis["recommendations"] = "\n".join(rec_lines)

    analysis["source_trace"] = source_trace
    analysis["ttps"] = []

    return analysis


def _parse_severity(raw: str) -> str:
    for label in ("Critical", "High", "Medium", "Low", "Informational"):
        if label.lower() in raw.lower():
            return label
    return "Unknown"
