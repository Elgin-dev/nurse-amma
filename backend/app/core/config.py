from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str
    ollama_chat_url: str = "http://localhost:11434/api/chat"
    ollama_model: str = "gemma3:1b"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    # Configure both values in the project-root .env file. There are deliberately
    # no insecure development defaults for signing or bootstrap secrets.
    jwt_secret_key: str | None = None
    bootstrap_admin_token: str | None = None
    access_token_expire_minutes: int = Field(default=60, gt=0, le=1440)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
