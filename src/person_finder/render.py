"""CLI entrypoint: fetch -> enrich -> print."""

from __future__ import annotations

import json
import sys

from groq import APIStatusError

from person_finder.agent import enrich_names
from person_finder.users import UserFetchError, fetch_user_names


def _extract_api_message(exc: APIStatusError) -> str:
    """Pull the human-readable message out of a Groq API error.

    `exc.message` is `"Error code: 429 - {body-as-dict-literal}"` — readable
    but ugly. The structured `exc.body` carries `{"error": {"message": ...}}`
    when Groq returned JSON; that inner string is the clean text we want
    (e.g. "Rate limit reached… Please try again in 1.23s."). Fall back to
    `exc.message` if the body shape is unexpected (non-JSON 5xx, etc.).
    """
    body = exc.body
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
    return exc.message


def main() -> None:
    try:
        names = fetch_user_names()
        payload = enrich_names(names)
    except APIStatusError as exc:
        # Rate-limit (429), context-length / bad-request (400), auth (401),
        # 5xx, etc. — Groq's own message is actionable (e.g. "try again in
        # 2.1s"), so surface it cleanly instead of a stack trace.
        print(f"Error: {_extract_api_message(exc)}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, UserFetchError):
        print("Could not respond — please try again later.", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    sys.exit(0)
