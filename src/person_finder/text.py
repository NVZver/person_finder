"""Shared UNKNOWN-sentinel handling for the identify and best-work stages."""

from __future__ import annotations

# Sentinel a model emits when it cannot identify the person / their work.
UNKNOWN_SENTINEL = "UNKNOWN"


def is_unknown(reply: str) -> bool:
    """Match the UNKNOWN sentinel, tolerating case, trailing dots, and empty replies."""
    normalized = reply.strip().rstrip(".").strip().upper()
    return normalized == "" or normalized == UNKNOWN_SENTINEL
