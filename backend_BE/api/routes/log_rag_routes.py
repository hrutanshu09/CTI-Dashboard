from fastapi import APIRouter, UploadFile, File, HTTPException
from services.log_rag_service import process_log_text
from pydantic import BaseModel
from services.rag_services import analyze_threat
from striprtf.striprtf import rtf_to_text
from utils.log_processing import normalize_logs, chunk_logs,process_log_chunks
import logging


router = APIRouter(prefix="/logs", tags=["Log RAG"])
logger = logging.getLogger(__name__)
SUPPORTED_TYPES = [".log", ".txt", ".rtf"]

class LogQuery(BaseModel):
    query: str

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

    result = analyze_threat(payload.query)

    return {"response": result}