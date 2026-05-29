"""Agent-facing LangChain tools — the agent's hands.

Two tools wrap the raw Wikipedia access in :mod:`person_finder.wikipedia`:
``lookup_person`` pulls a short bio slice for identification, and
``lookup_best_work`` pulls a longer slice for finding notable work. Both return
a usable string on a miss (never raise) so the agent can fall back to its own
knowledge.
"""

from __future__ import annotations

from langchain.tools import tool

from person_finder import config
from person_finder.wikipedia import fetch_wiki_summary


@tool
def lookup_person(name: str) -> str:
    """Look up who a person is on Wikipedia.

    Use this first to ground an identification in a source. Returns a short
    biographical summary, or a notice when no clean article match exists.
    """
    summary = fetch_wiki_summary(
        name,
        sentences=config.IDENTIFY_SENTENCES,
        char_cap=config.IDENTIFY_CHAR_CAP,
    )
    if summary is None:
        return f"No Wikipedia article found for '{name}'."
    return summary


@tool
def lookup_best_work(name: str) -> str:
    """Look up a person's most notable work or achievement on Wikipedia.

    Use this after identifying the person, to ground their best work in a
    source. Returns a longer article slice, or a notice when no clean article
    match exists.
    """
    summary = fetch_wiki_summary(
        name,
        sentences=config.TOOL_SENTENCES,
        char_cap=config.TOOL_CHAR_CAP,
    )
    if summary is None:
        return f"No Wikipedia article found for '{name}'."
    return summary
