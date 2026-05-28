"""CLI shim: enables `python -m person_finder`.

All logic lives in :mod:`person_finder.render`; this file is a one-liner so
the testable surface (and the orchestration) stays in `render.py`.
"""

from __future__ import annotations

from person_finder.render import main


if __name__ == "__main__":
    main()
