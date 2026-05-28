"""Top-level orchestrator: fetch -> enrich -> validate -> print.

Wires Epics 2, 3, and 4 into the user-facing CLI surface described in
[ARCHITECTURE.md](../../ARCHITECTURE.md) §Layers/1 lines 23-24 and §Data flow.
The pipeline is::

    users.fetch_user_names()
      -> agent.enrich_names(names)
        -> validation.validate_output(raw, repair_fn=agent.repair)
          -> print(json.dumps(payload, indent=2))

On the two named failure classes from [main.spec.md §Cross-Module
Contracts](../../specs/main.spec.md) — `validation.Error("Could not respond")`
(repair budget exhausted) and `users.UserFetchError` (upstream HTTP / parse
failure) — the entrypoint prints a single user-facing retry message to stderr
and exits non-zero. Python's default traceback is intentionally suppressed:
the user does not need to see an `httpx` or `validation._ValidationFailure`
stack to know "try again later".

NF — Side-effect-free import: collaborators are imported, but no settings
access, no HTTP, no LLM construction happens at import time. The pipeline
runs only inside :func:`main`. Mirrors `agent` NF2 / `validation` NF3.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from person_finder.agent import enrich_names, repair as _repair
from person_finder.users import UserFetchError, fetch_user_names
from person_finder.validation import Error, validate_output


USER_FACING_RETRY_MESSAGE = "Could not respond — please try again later."
"""Single literal surfaced for both validation.Error and users.UserFetchError.

Per the epic spec: no traceback, no Python exception class name leak, no
upstream HTTP status code. The user only needs the retry instruction.
"""


def _run() -> dict[str, Any]:
    """Run the full pipeline; raise through on either named failure class.

    Extracted so the error-handling boundary in :func:`main` stays tight:
    `_run` only raises `UserFetchError` or `validation.Error`; everything
    else (including the success payload) flows back through the return.
    """
    names = fetch_user_names()
    raw = enrich_names(names)
    # `repair_fn` MUST be a real callable (not None) — Epic 4's retry loop
    # is the contract validation.spec.md F4 hands off to this orchestrator.
    # `_repair` is `agent.repair`, re-exported as a private name to make the
    # binding swap-friendly in unit tests via `monkeypatch.setattr`.
    return validate_output(raw, repair_fn=_repair)


def main() -> None:
    """CLI entrypoint. Exits 0 on success, non-zero on either named failure.

    Defers SystemExit until after the print, so capture-based tests
    (`capsys`) can observe both the output and the exit code.
    """
    try:
        payload = _run()
    except (Error, UserFetchError):
        # Suppressed-traceback policy: the user-facing surface is one literal
        # line on stderr. `__cause__` still carries the precise diagnostic for
        # any future debug-flag epic (see Open Questions in the design brief).
        print(USER_FACING_RETRY_MESSAGE, file=sys.stderr)
        sys.exit(1)

    # `flush=True` so consumers piping stdout (e.g. `python -m person_finder | jq`)
    # see the document before the process exits.
    print(json.dumps(payload, indent=2), flush=True)
    sys.exit(0)
