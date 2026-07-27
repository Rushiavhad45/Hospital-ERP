"""Application configuration.

All runtime configuration lives here, sourced from environment variables /
an optional ``.env`` file. The JWT secret is never hard-coded: if it is not
supplied via the environment it is generated once and persisted to
``data/.secret_key`` (chmod 600) so tokens survive restarts.
"""
from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Dr. Palaskar Hospital ERP"
    ENV: str = "development"

    # --- security -----------------------------------------------------------
    SECRET_KEY: str = ""                      # HS256 symmetric key
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720    # 12h shift
    COOKIE_SECURE: bool = False               # set True behind HTTPS
    RATE_LIMIT_ENABLED: bool = True

    # --- storage ------------------------------------------------------------
    DATABASE_URL: str = f"sqlite+aiosqlite:///{(BASE_DIR / 'data' / 'hospital.db').as_posix()}"
    UPLOAD_DIR: str = str(BASE_DIR / "data" / "uploads")
    MAX_UPLOAD_MB: int = 10

    SEED_ON_STARTUP: bool = True

    def resolved_secret(self) -> str:
        """Return the configured secret, generating & persisting one if absent."""
        if self.SECRET_KEY:
            return self.SECRET_KEY
        key_file = BASE_DIR / "data" / ".secret_key"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        if key_file.exists():
            return key_file.read_text().strip()
        key = secrets.token_urlsafe(64)
        key_file.write_text(key)
        try:
            os.chmod(key_file, 0o600)
        except OSError:  # pragma: no cover - platform dependent
            pass
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()
