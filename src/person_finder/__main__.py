"""CLI shim: enables `python -m person_finder`."""

from __future__ import annotations

from person_finder.render import main


if __name__ == "__main__":
    main()
