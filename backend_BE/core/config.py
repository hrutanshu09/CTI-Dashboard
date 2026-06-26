from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        extra="ignore",
    )

    LLM_PROVIDER: str = "groq"
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    NVD_API_KEY: str | None = None
    AUTH_SESSION_SECRET: str = "change-me-in-production"
    AUTH_COOKIE_NAME: str = "cti_session"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_SESSION_DAYS: int = 7
    FRONTEND_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    MODEL_PREFERENCES: list[str] = [
        "models/gemini-2.5-flash",
        "models/gemini-1.5-pro",
        "models/gemini-1.5-flash",
    ]


settings = Settings()
