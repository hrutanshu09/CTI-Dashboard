import os
from RAG.retreival import retrieve_context
from fastapi import UploadFile
import logging

UPLOAD_FOLDER = "uploads"

logger = logging.getLogger(__name__)

def process_log_text(log_text: str):
    try:
        matches = retrieve_context(log_text, k=5)

        return {
            "query": log_text,
            "matches": matches
        }

    except Exception as e:
        logger.exception("Log RAG processing failed")
        raise RuntimeError("Log RAG processing failed") from e

def chunk_logs(log_lines, chunk_size=20):

    chunks = []
    temp = []

    for line in log_lines:
        temp.append(line.strip())

        if len(temp) >= chunk_size:
            chunks.append(" ".join(temp))
            temp = []

    if temp:
        chunks.append(" ".join(temp))

    return chunks
