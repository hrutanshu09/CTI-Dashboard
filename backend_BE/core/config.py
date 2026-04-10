from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        extra="ignore",
    )

    LLM_PROVIDER: str = "gemini"
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    GEMINI_API_KEY: str | None = None
    NVD_API_KEY: str | None = None
    MODEL_PREFERENCES: list[str] = [
        "models/gemini-2.5-flash",
        "models/gemini-1.5-pro",
        "models/gemini-1.5-flash",
    ]


settings = Settings()
