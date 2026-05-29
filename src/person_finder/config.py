"""Central configuration: constants and the LLM factory.

Static values live as module-level constants. Deployment-varying knobs
(`MODEL`, `MAX_PEOPLE`, `MAX_RETRIES`) are exposed as functions that load
`.env` and read the environment at call time — so importing this module never
touches disk or the environment (see the import-side-effect tests).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq

# --- LLM (static) ---
TEMPERATURE = 0.0
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_MAX_RETRIES = 3

# --- User fetch: randomuser.me (static) ---
RANDOMUSER_URL = "https://randomuser.me/api/?results=20"
BIRTH_YEAR_CUTOFF = 2000
REQUEST_TIMEOUT = 10.0
DEFAULT_MAX_PEOPLE = 5

# --- Wikipedia (static) ---
# Wikipedia rejects requests without a descriptive User-Agent (403 otherwise).
WIKI_USER_AGENT = "person_finder/0.1 (NN GenAI assessment; +https://randomuser.me)"
# The one-shot identify step needs less context than the agent's tool call.
IDENTIFY_SENTENCES = 3
IDENTIFY_CHAR_CAP = 600
TOOL_SENTENCES = 6
TOOL_CHAR_CAP = 1500


def _load_env() -> None:
    load_dotenv(Path.cwd() / ".env")


def model() -> str:
    """Identify/agent model — `MODEL` env override, else the 70B default.

    The 70B model refuses non-famous names and emits tool calls reliably; the
    8B instant model fabricates biographies and calls tools unreliably.
    Override only with that trade-off in mind.
    """
    _load_env()
    return os.environ.get("MODEL", DEFAULT_MODEL)


def max_people() -> int:
    """Cap on people per run — `MAX_PEOPLE` env override, else 5."""
    _load_env()
    return int(os.environ.get("MAX_PEOPLE", str(DEFAULT_MAX_PEOPLE)))


def max_retries() -> int:
    """LLM retry budget — `MAX_RETRIES` env override, else 3.

    Honors Groq's short Retry-After on transient throttling; persistent errors
    still surface fast to main.py's APIStatusError handler.
    """
    _load_env()
    return int(os.environ.get("MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))


def groq_api_key() -> str:
    """Return `GROQ_API_KEY` or raise `RuntimeError` if missing/blank."""
    _load_env()
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is required")
    return key


def build_llm() -> ChatGroq:
    """Construct the shared chat model — the one place `ChatGroq` is built."""
    return ChatGroq(
        model=model(),
        api_key=groq_api_key(),
        temperature=TEMPERATURE,
        max_retries=max_retries(),
        # Disable parallel tool calls: the model otherwise emits the structured
        # response (PersonResult) twice in one turn alongside the lookup tools,
        # which langchain rejects — leaving no `structured_response`.
        model_kwargs={"parallel_tool_calls": False},
    )
