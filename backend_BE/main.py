from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.rag_routes import router as rag_router
from api.routes.log_rag_routes import router as log_rag_routes
from api.routes.threat_report import router as threat_report_router
from api.routes.dashboard_metrics import router as dashboard_metrics_router
import logging

app = FastAPI(title="Cyber Threat Intelligence API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)



app.include_router(rag_router, prefix="/rag", tags=["RAG"])
app.include_router(log_rag_routes)  # Add this line to include log RAG routes
app.include_router(threat_report_router)  # Add this line to include threat report routes
app.include_router(dashboard_metrics_router)
