"""Load `GROQ_API_KEY` from the process env or a local `.env` file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def groq_api_key() -> str:
    """Return `GROQ_API_KEY` or raise `RuntimeError` if missing/blank."""
    load_dotenv(Path.cwd() / ".env")
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is required")
    return key
