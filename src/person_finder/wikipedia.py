"""Raw Wikipedia access — the data-access layer.

Talks to the `wikipedia` library and returns plain strings (or `None` on any
miss/error). Knows nothing about LangChain or the agent; the tool wrappers in
:mod:`person_finder.tools` build on top of this.
"""

from __future__ import annotations

import warnings

import wikipedia
from bs4 import GuessedAtParserWarning

from person_finder import config

wikipedia.set_user_agent(config.WIKI_USER_AGENT)

# The `wikipedia` library triggers GuessedAtParserWarning on every search;
# silence it to keep CLI stderr clean.
warnings.filterwarnings("ignore", category=GuessedAtParserWarning)


def fetch_wiki_summary(name: str, *, sentences: int, char_cap: int) -> str | None:
    """Return a Wikipedia summary for `name`, or `None` on any miss/error.

    `DisambiguationError` and `PageError` are the documented "no clean match"
    paths; we treat them — and any network/SSL failure — as "no article
    available" so the caller's fallback can take over.
    """
    try:
        summary = wikipedia.summary(name, sentences=sentences, auto_suggest=True)
    except wikipedia.exceptions.WikipediaException:
        return None
    except Exception:
        # Network/SSL errors etc. — same "no article" outcome.
        return None

    summary = summary.strip()
    if not summary:
        return None
    return summary[:char_cap]
