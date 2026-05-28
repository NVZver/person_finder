"""CLI entrypoint: fetch -> enrich -> validate -> print."""

from __future__ import annotations

import json
import sys

from person_finder.agent import enrich_names, repair
from person_finder.users import UserFetchError, fetch_user_names
from person_finder.validation import Error, validate_output


def main() -> None:
    try:
        names = fetch_user_names()
        raw = enrich_names(names)
        payload = validate_output(raw, repair_fn=repair)
    except (Error, UserFetchError):
        print("Could not respond — please try again later.", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    sys.exit(0)
