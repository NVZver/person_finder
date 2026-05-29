"""CLI entrypoint: fetch -> log names (Ex2) -> agent lookup -> print JSON."""

from __future__ import annotations

import json
import sys

from groq import APIStatusError

from person_finder.person_lookup_agent import lookup_people
from person_finder.person_loader import UserFetchError, fetch_user_names


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


def _format_names(names: list[str]) -> str:
    """Render the Ex2 array-of-strings exactly as the assignment example shows."""
    lines = ",\n".join(f"  '{name}'" for name in names)
    return f"[\n{lines}\n]"


def main() -> None:
    try:
        names = fetch_user_names()
        # Ex2: log the formatted names array to the console. stderr keeps stdout
        # a clean, pipeable JSON document.
        print(_format_names(names), file=sys.stderr, flush=True)
        payload = lookup_people(names)
    except APIStatusError as exc:
        # Surface Groq's own actionable message instead of a stack trace.
        print(f"Error: {_extract_api_message(exc)}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, UserFetchError):
        print("Could not respond — please try again later.", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    sys.exit(0)
