"""Shared text helpers for the identify (Ex4) and best-work (Ex5) stages.

Lives in its own module so both :mod:`person_finder.agent` and
:mod:`person_finder.best_work_agent` can import the UNKNOWN handling without
creating an import cycle between them.
"""

from __future__ import annotations

# Sentinel a model must emit when it cannot identify the person / their work.
# Comparison is permissive (case- and punctuation-insensitive) to survive
# minor model serialization noise.
UNKNOWN_SENTINEL = "UNKNOWN"


def is_unknown(reply: str) -> bool:
    """Permissive match for the UNKNOWN sentinel.

    Tolerates trailing punctuation and case variation so a model that emits
    ``"unknown."`` or ``"Unknown"`` (or an empty reply) still routes to the
    null path instead of being treated as a positive answer.
    """
    normalized = reply.strip().rstrip(".").strip().upper()
    return normalized == "" or normalized == UNKNOWN_SENTINEL
