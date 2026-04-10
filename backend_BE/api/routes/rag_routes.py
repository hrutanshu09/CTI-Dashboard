from fastapi import APIRouter
from pydantic import BaseModel
from services.rag_services import analyze_threat

router = APIRouter()


class ThreatRequest(BaseModel):
    query: str


@router.post("/analyze")
async def analyze(request: ThreatRequest):

    result = analyze_threat(request.query)

    return {
        "query": request.query,
        "analysis": result
    }
