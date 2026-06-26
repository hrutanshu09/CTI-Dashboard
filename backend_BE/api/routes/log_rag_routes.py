from fastapi import APIRouter, UploadFile, File, HTTPException
from services.log_rag_service import process_log_text
from pydantic import BaseModel
from services.rag_services import answer_followup_question
from striprtf.striprtf import rtf_to_text
from utils.log_processing import normalize_logs, chunk_logs,process_log_chunks
from services.dashboard_metrics_service import metrics_store
import logging


router = APIRouter(prefix="/logs", tags=["Log RAG"])
logger = logging.getLogger(__name__)
SUPPORTED_TYPES = [".log", ".txt", ".rtf", ".csv"]

class LogQuery(BaseModel):
    query: str
    processed_context: str = ""

'''@router.post("/analyze")
async def analyze_log(file: UploadFile = File(...)):
    content = await file.read()
    log_text = content.decode("utf-8", errors="ignore")

    return process_log_text(log_text)'''

@router.post("/analyze")
async def analyze_log(file: UploadFile = File(...)):
    try:

        # ---------- Validate filename ----------
        filename = file.filename.lower()

        if not any(filename.endswith(ext) for ext in SUPPORTED_TYPES):
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type"
            )

        # ---------- Read file ----------
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )

        # ---------- Parse file ----------
        if filename.endswith(".rtf"):
            log_text = rtf_to_text(content.decode(errors="ignore"))
        else:
            log_text = content.decode("utf-8", errors="ignore")

        # ---------- Normalize ----------
        log_text = normalize_logs(log_text)

        # ---------- Chunk logs ----------
        chunks = chunk_logs(log_text)

        # ---------- Send to RAG ----------
        result = process_log_chunks(chunks)
        try:
            metrics_store.record_log_analysis(
                filename=file.filename or "uploaded_log",
                chunk_results=result,
            )
        except Exception:
            logger.exception("Dashboard metrics ingestion failed for log file: %s", file.filename)

        return {
            "status": "success",
            "chunks_processed": len(chunks),
            "analysis": result
        }

    except Exception as e:
        logger.exception("Log analysis failed")

        raise HTTPException(
            status_code=500,
            detail=f"Log analysis failed: {str(e)}"
        )



@router.post("/query")
async def query_logs(payload: LogQuery):

    result = answer_followup_question(
        payload.query,
        processed_context=payload.processed_context,
        retrieve_mode="global",
    )

    return {"response": result}
