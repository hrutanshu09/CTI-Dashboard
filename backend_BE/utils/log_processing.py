import re
from services.log_rag_service import process_log_text
import logging

logger = logging.getLogger(__name__)

def normalize_logs(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def chunk_logs(text, chunk_size=500):

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    chunks = []
    current = []

    for line in lines:
        current.append(line)

        if len(" ".join(current)) > chunk_size:
            chunks.append("\n".join(current))
            current = []

    if current:
        chunks.append("\n".join(current))

    return chunks

def process_log_chunks(chunks):
    responses = []

    for i, chunk in enumerate(chunks):

        # 🔥 Production guard
        if not chunk or not chunk.strip():
            continue

        try:
            response = process_log_text(chunk)

            responses.append({
                "chunk_id": i,
                "analysis": response
            })

        except Exception as e:
            logger.error(f"Chunk {i} failed: {e}")

    return responses
