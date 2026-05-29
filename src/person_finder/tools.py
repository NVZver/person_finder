"""Wikipedia access: a plain fetch helper and the LangChain tool wrapping it.

:func:`fetch_wiki_summary` is called directly by the identify step;
:data:`wikipedia_lookup` is the tool the best-work agent calls.
"""

from __future__ import annotations

import warnings

import wikipedia
from bs4 import GuessedAtParserWarning
from langchain.tools import tool

# Wikipedia rejects requests without a descriptive User-Agent (403 otherwise).
wikipedia.set_user_agent(
    "person_finder/0.1 (NN GenAI assessment; +https://randomuser.me)"
)

# The `wikipedia` library triggers GuessedAtParserWarning on every search;
# silence it to keep CLI stderr clean.
warnings.filterwarnings("ignore", category=GuessedAtParserWarning)


def fetch_wiki_summary(
    name: str, *, sentences: int, char_cap: int
) -> str | None:
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


# The agent needs more context than the one-shot identify step, so the tool
# pulls a longer slice of the article.
_TOOL_SENTENCES = 6
_TOOL_CHAR_CAP = 1500


@tool
def wikipedia_lookup(name: str) -> str:
    """Look up a person on Wikipedia and return article summary text.

    Use this to ground claims about who a person is and what they are known
    for. Returns a short notice when no clean article match exists.
    """
    summary = fetch_wiki_summary(
        name, sentences=_TOOL_SENTENCES, char_cap=_TOOL_CHAR_CAP
    )
    if summary is None:
        return f"No Wikipedia article found for '{name}'."
    return summary
