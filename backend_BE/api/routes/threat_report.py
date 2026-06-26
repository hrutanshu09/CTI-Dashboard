from typing import Literal, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from services.rag_services import answer_followup_question
from services.report_processing import (
    chunk_report,
    ingest_report_into_global_kb,
    normalize_report,
    process_report_chunks,
)
from services.dashboard_metrics_service import metrics_store
import logging

try:
    import fitz  # PyMuPDF

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


router = APIRouter(prefix="/threat-reports", tags=["Threat Report RAG"])
logger = logging.getLogger(__name__)

SUPPORTED_TYPES = [".pdf", ".txt", ".log"]


class ReportQuery(BaseModel):
    query: str
    report_id: Optional[str] = None
    mode: Literal["hybrid", "report_only", "global_only"] = "hybrid"
    processed_context: str = ""


def _extract_pdf_text(raw_bytes: bytes) -> str:
    if not PDF_SUPPORT:
        raise HTTPException(
            status_code=501,
            detail="PDF support unavailable. Install with: pip install pymupdf",
        )

    with fitz.open(stream=raw_bytes, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


@router.post("/analyze")
async def analyze_threat_report(file: UploadFile = File(...)):
    """
    Upload a threat report (.pdf, .txt, .log).

    Returns:
      - iocs: Extracted IPs, domains, hashes, CVEs
      - severity: Critical / High / Medium / Low / Informational
      - analysis: Structured threat-report analysis
      - ingest: report_id and ingestion metadata for follow-up scoped queries
    """
    try:
        filename = (file.filename or "").lower()
        if not any(filename.endswith(ext) for ext in SUPPORTED_TYPES):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Accepted: {', '.join(SUPPORTED_TYPES)}",
            )

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        if filename.endswith(".pdf"):
            raw_text = _extract_pdf_text(content)
        else:
            raw_text = content.decode("utf-8", errors="ignore")

        if not raw_text.strip():
            raise HTTPException(
                status_code=422,
                detail="No text could be extracted from the uploaded file.",
            )

        report_text = normalize_report(raw_text)
        chunks = chunk_report(report_text)

        ingest = ingest_report_into_global_kb(
            raw_bytes=content,
            filename=file.filename or "uploaded_report",
            chunks=chunks,
        )

        result = process_report_chunks(
            chunks,
            report_id=ingest["report_id"],
            retrieval_mode="hybrid",
        )
        try:
            metrics_store.record_threat_report_analysis(
                filename=file.filename or "uploaded_report",
                report_id=ingest["report_id"],
                severity=result.get("severity", "Unknown"),
                iocs=result.get("iocs", {}),
                analysis=result.get("analysis", {}),
            )
        except Exception:
            logger.exception("Dashboard metrics ingestion failed for threat report: %s", file.filename)

        return {
            "status": "success",
            "filename": file.filename,
            "chunks_processed": len(chunks),
            "report_id": ingest["report_id"],
            "ingest": ingest,
            "iocs": result["iocs"],
            "severity": result["severity"],
            "analysis": result["analysis"],
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Threat report analysis failed for: %s", file.filename)
        raise HTTPException(status_code=500, detail="Threat report analysis failed.")


@router.post("/query")
async def query_threat_report(payload: ReportQuery):
    """
    Ask a question using one of three modes:
      - report_only: retrieve only from uploaded report (requires report_id)
      - global_only: retrieve only from global KB
      - hybrid: mix report + global (requires report_id)
    """
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    if payload.mode in {"report_only", "hybrid"} and not payload.report_id:
        raise HTTPException(
            status_code=400,
            detail="report_id is required when mode is 'report_only' or 'hybrid'.",
        )

    retrieve_mode = {
        "report_only": "report_only",
        "global_only": "global",
        "hybrid": "hybrid",
    }[payload.mode]

    try:
        result = answer_followup_question(
            payload.query,
            processed_context=payload.processed_context,
            report_id=payload.report_id,
            strict_report=payload.mode == "report_only",
            retrieve_mode=retrieve_mode,
        )
        return {
            "response": result,
            "report_id": payload.report_id,
            "mode": payload.mode,
            "scope": retrieve_mode,
        }
    except Exception:
        logger.exception("Threat report query failed")
        raise HTTPException(status_code=500, detail="Query execution failed.")
