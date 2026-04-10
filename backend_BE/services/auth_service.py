from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.config import settings


class AuthService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    google_sub TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    picture_url TEXT,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_hash TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_hash ON sessions(session_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
            conn.commit()

    def upsert_google_user(self, claims: dict[str, Any]) -> dict[str, Any]:
        google_sub = str(claims.get("sub") or "").strip()
        email = str(claims.get("email") or "").strip().lower()
        if not google_sub or not email:
            raise ValueError("Google identity payload is missing required fields.")

        now = _utc_now_iso()
        name = str(claims.get("name") or "").strip()
        picture_url = str(claims.get("picture") or "").strip()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id FROM users WHERE google_sub = ?",
                (google_sub,),
            ).fetchone()

            if row:
                conn.execute(
                    """
                    UPDATE users
                    SET email = ?, name = ?, picture_url = ?, last_login_at = ?
                    WHERE google_sub = ?
                    """,
                    (email, name, picture_url, now, google_sub),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO users (google_sub, email, name, picture_url, created_at, last_login_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (google_sub, email, name, picture_url, now, now),
                )
            conn.commit()

            user = conn.execute(
                """
                SELECT id, google_sub, email, name, picture_url, created_at, last_login_at
                FROM users
                WHERE google_sub = ?
                """,
                (google_sub,),
            ).fetchone()

        return dict(user) if user else {}

    def create_session(self, user_id: int) -> tuple[str, datetime]:
        raw_token = secrets.token_urlsafe(48)
        expires_at = datetime.now(UTC) + timedelta(days=max(1, settings.AUTH_SESSION_DAYS))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (user_id, session_hash, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, _hash_token(raw_token), _utc_now_iso(), expires_at.isoformat()),
            )
            conn.commit()
        return raw_token, expires_at

    def get_user_from_session(self, raw_token: str | None) -> dict[str, Any] | None:
        if not raw_token:
            return None
        now = datetime.now(UTC)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT u.id, u.google_sub, u.email, u.name, u.picture_url, u.created_at, u.last_login_at, s.expires_at
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_hash = ?
                """,
                (_hash_token(raw_token),),
            ).fetchone()

            if not row:
                return None

            expires_at = datetime.fromisoformat(str(row["expires_at"]))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

            if expires_at <= now:
                conn.execute("DELETE FROM sessions WHERE session_hash = ?", (_hash_token(raw_token),))
                conn.commit()
                return None

            return {
                "id": row["id"],
                "google_sub": row["google_sub"],
                "email": row["email"],
                "name": row["name"],
                "picture_url": row["picture_url"],
                "created_at": row["created_at"],
                "last_login_at": row["last_login_at"],
            }

    def revoke_session(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE session_hash = ?", (_hash_token(raw_token),))
            conn.commit()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


auth_service = AuthService(db_path=Path(__file__).resolve().parents[1] / "data" / "auth.db")
