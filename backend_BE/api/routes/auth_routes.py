from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel

from core.config import settings
from services.auth_service import auth_service


router = APIRouter(prefix="/auth", tags=["Authentication"])


class GoogleLoginRequest(BaseModel):
    credential: str


def _cookie_kwargs(max_age: int = 0) -> dict:
    kwargs = {
        "key": settings.AUTH_COOKIE_NAME,
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": "lax",
        "path": "/",
    }
    if max_age > 0:
        kwargs["max_age"] = max_age
    return kwargs


@router.post("/google")
def login_with_google(payload: GoogleLoginRequest, response: Response):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID is not configured on the backend.",
        )

    try:
        claims = google_id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential.") from exc

    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google issuer.")

    user = auth_service.upsert_google_user(claims)
    session_token, expires_at = auth_service.create_session(user_id=int(user["id"]))

    max_age = int((expires_at - datetime.now(UTC)).total_seconds())
    response.set_cookie(**_cookie_kwargs(max_age=max(1, max_age)), value=session_token)

    return {
        "user": user,
        "authenticated": True,
    }


@router.get("/me")
def me(request: Request):
    session_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    user = auth_service.get_user_from_session(session_token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return {"user": user, "authenticated": True}


@router.post("/logout")
def logout(request: Request, response: Response):
    session_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    auth_service.revoke_session(session_token)
    response.delete_cookie(**_cookie_kwargs())
    return {"ok": True}
