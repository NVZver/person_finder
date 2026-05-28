"""Typed application settings.

Both keys are required and non-blank. Values come from the process env first,
then from a `.env` file in the CWD. Instantiating `Settings()` raises
`pydantic.ValidationError` if either is missing.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    groq_api_key: str = Field(min_length=1)
    google_api_key: str = Field(min_length=1)
