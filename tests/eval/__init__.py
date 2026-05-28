"""tests.eval — DeepEval LLM-judge evaluation suite.

This package's `conftest.py` owns the runtime wiring (fixtures, autouse
re-set of the API keys the root conftest strips, lazy Gemini-judge
configuration, lazy agent import). A few small helpers live here at
package scope so they remain trivially importable from test modules
(conftest files are pytest plugins and not stably importable by their
dotted path); keeping the helpers minimal preserves the "empty marker"
spirit of the package init while making fixture state testable.
"""

from __future__ import annotations

import os
from typing import NamedTuple


class RealKeys(NamedTuple):
    """Snapshot of the project's two API keys captured before isolation.

    Both fields default to whatever `os.environ.get(...)` returned at
    capture time: `str` when the host shell had the key set (including
    `""` for a set-but-blank var), or `None` when the key was absent.
    """

    groq_api_key: str | None
    google_api_key: str | None


def _capture_real_keys() -> RealKeys:
    """Read the host env once. Called at conftest import time.

    Must run BEFORE the root `tests/conftest.py` autouse `_isolate_env`
    fixture deletes the keys. Pytest imports `conftest.py` files during
    collection, which happens before any test fixture executes — so this
    snapshot reflects the developer's true shell environment.
    """
    return RealKeys(
        groq_api_key=os.environ.get("GROQ_API_KEY"),
        google_api_key=os.environ.get("GOOGLE_API_KEY"),
    )
