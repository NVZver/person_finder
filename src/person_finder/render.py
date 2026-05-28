"""CLI entrypoint: fetch -> enrich -> print."""

from __future__ import annotations

import json
import sys

from person_finder.agent import enrich_names
from person_finder.users import UserFetchError, fetch_user_names


def main() -> None:
    try:
        names = fetch_user_names()
        payload = enrich_names(names)
    except (json.JSONDecodeError, UserFetchError):
        print("Could not respond — please try again later.", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    sys.exit(0)
