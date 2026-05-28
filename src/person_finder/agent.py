"""Identify each name with Wikipedia + LLM in a deterministic per-name loop.

For each input name we control the source attribution programmatically:

  1. Try `wikipedia.summary(name)`. On hit → ask the LLM to compress to
     1-2 sentences. Source = ``"wiki"``.
  2. On miss → ask the LLM to identify the person from training knowledge.
     If the LLM responds with the literal ``UNKNOWN`` sentinel → both
     ``info`` and ``source`` are ``null``. Else → ``source = "llm"`` and
     ``info`` is the LLM's reply.

The LLM never decides the ``source`` field or whether ``info`` is ``null`` —
those are derived from which retrieval step succeeded. This eliminates the
entire class of "LLM emits the string `'null'` instead of JSON `null`" and
"LLM forgets the source tag" failure modes that a structured-output contract
exposes.

Each LLM invocation is a one-shot text-in / text-out call: no tool use, no
JSON envelope to parse, no repair-retry loop. Cost trade-off vs the prior
single batched agent invocation: more API round-trips per run, but each is
small and the output is reliably parseable.
"""

from __future__ import annotations

import warnings
from typing import Any

import wikipedia
from bs4 import GuessedAtParserWarning
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from person_finder.config import groq_api_key

# Wikipedia's robot policy rejects requests without a descriptive User-Agent;
# the python-`wikipedia` library's default UA gets a 403.
wikipedia.set_user_agent(
    "person_finder/0.1 (NN GenAI assessment; +https://randomuser.me)"
)

# The `wikipedia` library calls `BeautifulSoup(html)` without an explicit
# parser, which prints `GuessedAtParserWarning` on every search. Upstream
# noise (goldsmith/Wikipedia#207) — silence it so CLI stderr stays clean
# for actual error messages.
warnings.filterwarnings("ignore", category=GuessedAtParserWarning)

# Sentinel the LLM must emit when it cannot identify the person from training
# knowledge. Comparison is permissive (case- and punctuation-insensitive) to
# survive minor model serialization noise.
UNKNOWN_SENTINEL = "UNKNOWN"

_WIKI_SENTENCES = 3
_SUMMARY_CHAR_CAP = 600


SUMMARIZE_PROMPT = """Summarize the following Wikipedia content about a person in 1-2 sentences.
Focus on who they are and what they're best known for. Return ONLY the
summary text — no preamble, no quotes, no JSON.

{content}"""

IDENTIFY_PROMPT = """Identify the person named "{name}" in 1-2 sentences from your training
knowledge. Focus on who they are and what they're best known for.

If you cannot confidently identify a specific real person with this name,
respond with exactly the single word UNKNOWN (no punctuation, no other text).

Return ONLY the summary OR the word UNKNOWN."""


def _model() -> ChatGroq:
    return ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=groq_api_key(),
        temperature=0,
        # Surface 429s immediately so render.py's APIStatusError handler can
        # print Groq's actionable "try again in Ns" message. The SDK default
        # of 2 retries with backoff hangs silently for ~30s before raising.
        max_retries=0,
    )


def _fetch_wiki(name: str) -> str | None:
    """Return a Wikipedia summary for `name`, or `None` on any miss/error.

    `DisambiguationError` and `PageError` are the documented "no clean
    match" paths; we treat them as "no article available" so the LLM
    fallback takes over. Network/HTTP failures also return `None` — they
    shouldn't fail the whole batch.
    """
    try:
        summary = wikipedia.summary(
            name, sentences=_WIKI_SENTENCES, auto_suggest=True
        )
    except wikipedia.exceptions.WikipediaException:
        return None
    except Exception:
        # Network/SSL errors etc. — same "no article" outcome.
        return None

    summary = summary.strip()
    if not summary:
        return None
    return summary[:_SUMMARY_CHAR_CAP]


def _summarize_article(llm: Any, content: str) -> str:
    reply = llm.invoke(
        [HumanMessage(content=SUMMARIZE_PROMPT.format(content=content))]
    )
    return reply.content.strip()


def _identify_from_memory(llm: Any, name: str) -> str | None:
    """Ask the LLM to identify `name` from training knowledge, or `None`."""
    reply = llm.invoke(
        [HumanMessage(content=IDENTIFY_PROMPT.format(name=name))]
    )
    text = reply.content.strip()
    if _is_unknown(text):
        return None
    return text


def _is_unknown(reply: str) -> bool:
    """Permissive match for the UNKNOWN sentinel.

    Tolerates trailing punctuation and case variation so a model that
    emits ``"unknown."`` or ``"Unknown"`` still routes to the null pair
    instead of being treated as a positive identification.
    """
    normalized = reply.strip().rstrip(".").strip().upper()
    return normalized == "" or normalized == UNKNOWN_SENTINEL


def enrich_names(names: list[str], *, model: Any | None = None) -> dict[str, Any]:
    """Identify each name; return ``{"data": [{person, info, source}]}``.

    Per-name: wiki summary → if hit, LLM compresses to 1-2 sentences with
    ``source="wiki"``; if miss, LLM identifies from memory and we set
    ``source="llm"`` or null based on whether it emitted the UNKNOWN
    sentinel. Paired nullability is guaranteed by construction.
    """
    llm = model if model is not None else _model()
    rows: list[dict[str, Any]] = []
    for name in names:
        article = _fetch_wiki(name)
        if article is not None:
            info = _summarize_article(llm, article)
            rows.append({"person": name, "info": info, "source": "wiki"})
            continue

        identification = _identify_from_memory(llm, name)
        if identification is None:
            rows.append({"person": name, "info": None, "source": None})
        else:
            rows.append({"person": name, "info": identification, "source": "llm"})
    return {"data": rows}
