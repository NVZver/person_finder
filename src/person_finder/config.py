"""Application configuration.

Both keys are required and non-blank. Reading is delegated to pydantic-settings,
which sources values from process env first, then from a `.env` file in the CWD.

Production code should call `get_settings()` (cached per-process). Tests should
construct `Settings()` directly under `monkeypatch.setenv`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Raises `pydantic.ValidationError` on instantiation if either key is missing
    or blank — this is the project's fail-loud contract.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    groq_api_key: str = Field(min_length=1)
    google_api_key: str = Field(min_length=1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached `Settings` instance."""
    return Settings()
