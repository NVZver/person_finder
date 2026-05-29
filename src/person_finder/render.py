"""CLI entrypoint: fetch -> enrich -> print."""

from __future__ import annotations

import json
import sys

from groq import APIStatusError

from person_finder.agent import enrich_names
from person_finder.users import UserFetchError, fetch_user_names


def _extract_api_message(exc: APIStatusError) -> str:
    """Return the clean message from `exc.body["error"]["message"]`, or `exc.message`."""
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
        # Surface Groq's own actionable message instead of a stack trace.
        print(f"Error: {_extract_api_message(exc)}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, UserFetchError):
        print("Could not respond — please try again later.", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    sys.exit(0)
