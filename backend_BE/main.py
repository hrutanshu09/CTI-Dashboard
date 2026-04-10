from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api.routes.rag_routes import router as rag_router
from api.routes.log_rag_routes import router as log_rag_routes
from api.routes.threat_report import router as threat_report_router
from api.routes.dashboard_metrics import router as dashboard_metrics_router
from api.routes.auth_routes import router as auth_router
from core.config import settings
from services.auth_service import auth_service
import logging

app = FastAPI(title="Cyber Threat Intelligence API")

frontend_origins = [origin.strip() for origin in settings.FRONTEND_ORIGINS.split(",") if origin.strip()]

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins or ["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


@app.on_event("startup")
async def on_startup():
    auth_service.init_db()


@app.middleware("http")
async def auth_guard(request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or path.startswith("/auth") or path in {"/docs", "/openapi.json", "/redoc"}:
        return await call_next(request)

    session_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    user = auth_service.get_user_from_session(session_token)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Authentication required."})

    request.state.user = user
    return await call_next(request)


app.include_router(rag_router, prefix="/rag", tags=["RAG"])
app.include_router(log_rag_routes)  # Add this line to include log RAG routes
app.include_router(threat_report_router)  # Add this line to include threat report routes
app.include_router(dashboard_metrics_router)
app.include_router(auth_router)
