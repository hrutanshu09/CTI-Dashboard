from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from core.config import settings
from services.auth_service import auth_service


router = APIRouter(prefix="/auth", tags=["Authentication"])


class SignupRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


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


def _set_session_cookie(response: Response, user_id: int) -> None:
    session_token, expires_at = auth_service.create_session(user_id=user_id)
    max_age = int((expires_at - datetime.now(UTC)).total_seconds())
    response.set_cookie(**_cookie_kwargs(max_age=max(1, max_age)), value=session_token)


@router.post("/signup")
def signup(payload: SignupRequest, response: Response):
    try:
        user = auth_service.create_local_user(
            email=payload.email,
            password=payload.password,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _set_session_cookie(response, user_id=int(user["id"]))

    return {
        "user": user,
        "authenticated": True,
    }


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    user = auth_service.authenticate_local_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    _set_session_cookie(response, user_id=int(user["id"]))

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
