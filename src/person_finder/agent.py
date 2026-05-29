"""Identify each name and research their best work, source-tagged per row.

Per name: try ``wikipedia.summary(name)``; on a hit the LLM compresses it
(``source="wiki"``), on a miss the LLM identifies from training knowledge
(``source="llm"``) or emits ``UNKNOWN`` → the null pair. ``source`` and
``info`` nullability are derived from which retrieval step succeeded, never
chosen by the LLM. Each identified person is then passed to the best-work
agent (:mod:`person_finder.best_work_agent`). Each row is
``{person, info, source, best_work}``.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from person_finder.best_work_agent import research_best_work
from person_finder.config import groq_api_key
from person_finder.text import UNKNOWN_SENTINEL, is_unknown
from person_finder.tools import fetch_wiki_summary

__all__ = ["enrich_names", "UNKNOWN_SENTINEL"]

_WIKI_SENTENCES = 3
_SUMMARY_CHAR_CAP = 600


SUMMARIZE_PROMPT = """Summarize the following Wikipedia content about a person in 1-2 sentences.
Focus on who they are and what they're best known for. Return ONLY the
summary text — no preamble, no quotes, no JSON.

If the content is not actually about an identifiable, real person (for example
it is a disambiguation list, a place or thing, or says nothing specific about
any one person), respond with exactly the single word UNKNOWN.

{content}"""

IDENTIFY_PROMPT = """You are checking whether "{name}" is a well-known public figure.

These names come from a random generator, so MOST of them belong to ordinary,
non-famous people. For those you MUST answer UNKNOWN.

Only if "{name}" is a genuinely notable public figure you can identify with
high confidence (a widely recognized scientist, artist, author, leader,
athlete, etc.) should you reply with 1-2 sentences on who they are and what
they are best known for.

If you are not highly confident that this is a specific, real, notable person,
respond with exactly the single word UNKNOWN (no punctuation, no other text).

Return ONLY the 1-2 sentence summary OR the word UNKNOWN."""


# The 70B model refuses non-famous names reliably; the 8B instant model
# fabricates confident biographies for them.
IDENTIFY_MODEL = "llama-3.3-70b-versatile"


def _model() -> ChatGroq:
    return ChatGroq(
        model=IDENTIFY_MODEL,
        api_key=groq_api_key(),
        temperature=0,
        # Honor Groq's short Retry-After on transient throttling; persistent
        # errors still surface fast to render.py's APIStatusError handler.
        max_retries=2,
    )


def _summarize_article(llm: Any, content: str) -> str | None:
    """Compress a Wikipedia article to 1-2 sentences, or `None`.

    `None` when the LLM judges the content is not actually about an
    identifiable real person — the case where `auto_suggest` landed on a
    disambiguation page or an unrelated article for a fictional name.
    """
    reply = llm.invoke(
        [HumanMessage(content=SUMMARIZE_PROMPT.format(content=content))]
    )
    text = reply.content.strip()
    if is_unknown(text):
        return None
    return text


def _identify_from_memory(llm: Any, name: str) -> str | None:
    """Ask the LLM to identify `name` from training knowledge, or `None`."""
    reply = llm.invoke(
        [HumanMessage(content=IDENTIFY_PROMPT.format(name=name))]
    )
    text = reply.content.strip()
    if is_unknown(text):
        return None
    return text


def _identify(llm: Any, name: str) -> tuple[str | None, str | None]:
    """Return ``(info, source)`` for `name`. Both null when unidentified."""
    article = fetch_wiki_summary(
        name, sentences=_WIKI_SENTENCES, char_cap=_SUMMARY_CHAR_CAP
    )
    if article is not None:
        summary = _summarize_article(llm, article)
        if summary is not None:
            return summary, "wiki"
        # Article wasn't an identifiable person (e.g. a disambiguation page);
        # don't fall through to the memory path — return the null pair.
        return None, None

    identification = _identify_from_memory(llm, name)
    if identification is None:
        return None, None
    return identification, "llm"


def enrich_names(
    names: list[str],
    *,
    model: Any | None = None,
    best_work_agent: Any | None = None,
    with_best_work: bool = True,
) -> dict[str, Any]:
    """Identify each name and research their best work.

    Returns ``{"data": [{person, info, source, best_work}]}``.

    `model` overrides the identify-step LLM; `best_work_agent` overrides the
    Ex5 agent graph — both for tests, so the pipeline runs fully offline.
    `with_best_work=False` skips the agentic stage (e.g. identify-only runs).
    The best-work agent runs only for identified people; unidentified rows
    carry ``best_work=None``.
    """
    llm = model if model is not None else _model()
    rows: list[dict[str, Any]] = []
    for name in names:
        info, source = _identify(llm, name)

        if info is not None and with_best_work:
            best_work = research_best_work(name, agent=best_work_agent)
        else:
            best_work = None

        rows.append(
            {
                "person": name,
                "info": info,
                "source": source,
                "best_work": best_work,
            }
        )
    return {"data": rows}
