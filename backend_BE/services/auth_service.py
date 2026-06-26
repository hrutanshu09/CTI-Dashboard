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
            self._migrate_legacy_users_table(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    google_sub TEXT UNIQUE,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    picture_url TEXT,
                    password_hash TEXT,
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

    def _migrate_legacy_users_table(self, conn: sqlite3.Connection) -> None:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()
        if not table:
            return

        columns = conn.execute("PRAGMA table_info(users)").fetchall()
        column_names = {str(column[1]) for column in columns}
        google_sub_column = next((column for column in columns if str(column[1]) == "google_sub"), None)
        google_sub_not_null = bool(google_sub_column and int(google_sub_column[3]) == 1)

        if "password_hash" in column_names and not google_sub_not_null:
            return

        conn.execute("ALTER TABLE users RENAME TO users_legacy_google")

    def create_local_user(self, email: str, password: str, name: str = "") -> dict[str, Any]:
        email = _normalize_email(email)
        name = str(name or "").strip()
        if not email:
            raise ValueError("Email is required.")
        if len(password or "") < 6:
            raise ValueError("Password must be at least 6 characters.")

        now = _utc_now_iso()
        password_hash = _hash_password(password)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                conn.execute(
                    """
                    INSERT INTO users (email, name, picture_url, password_hash, created_at, last_login_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (email, name, "", password_hash, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("An account with this email already exists.") from exc
            conn.commit()

            user = conn.execute(
                """
                SELECT id, email, name, picture_url, created_at, last_login_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

        return dict(user) if user else {}

    def authenticate_local_user(self, email: str, password: str) -> dict[str, Any] | None:
        email = _normalize_email(email)
        if not email or not password:
            return None

        now = _utc_now_iso()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, email, name, picture_url, password_hash, created_at, last_login_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

            if not row or not _verify_password(password, str(row["password_hash"] or "")):
                return None

            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, row["id"]))
            conn.commit()

            user = dict(row)
            user.pop("password_hash", None)
            user["last_login_at"] = now
            return user

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
                SELECT u.id, u.email, u.name, u.picture_url, u.created_at, u.last_login_at, s.expires_at
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


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(rounds),
        )
        return secrets.compare_digest(digest.hex(), expected)
    except Exception:
        return False


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


auth_service = AuthService(db_path=Path(__file__).resolve().parents[1] / "data" / "auth.db")
