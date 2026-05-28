"""Top-level orchestrator: fetch -> enrich -> validate -> print.

The pipeline is::

    users.fetch_user_names()
      -> agent.enrich_names(names)
        -> validation.validate_output(raw, repair_fn=agent.repair)
          -> print(json.dumps(payload, indent=2))

On the two named failure classes — `validation.Error("Could not respond")`
(repair budget exhausted) and `users.UserFetchError` (upstream HTTP / parse
failure) — the entrypoint prints a single user-facing retry message to stderr
and exits non-zero. Python's default traceback is intentionally suppressed:
the user does not need to see an `httpx` or `validation._ValidationFailure`
stack to know "try again later".

Side-effect-free import: collaborators are imported, but no settings access,
no HTTP, no LLM construction happens at import time. The pipeline runs only
inside :func:`main`.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from person_finder.agent import enrich_names, repair as _repair
from person_finder.users import UserFetchError, fetch_user_names
from person_finder.validation import Error, validate_output


USER_FACING_RETRY_MESSAGE = "Could not respond — please try again later."


def _run() -> dict[str, Any]:
    """Run the full pipeline; raise through on either named failure class."""
    names = fetch_user_names()
    raw = enrich_names(names)
    return validate_output(raw, repair_fn=_repair)


def main() -> None:
    """CLI entrypoint. Exits 0 on success, non-zero on either named failure."""
    try:
        payload = _run()
    except (Error, UserFetchError):
        print(USER_FACING_RETRY_MESSAGE, file=sys.stderr)
        sys.exit(1)

    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    sys.exit(0)
