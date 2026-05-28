"""Identify each name via a Groq LLM with a `wikipedia_search` tool.

The agent follows a three-step fallback ladder per name:

  1. Call `wikipedia_search` (primary, grounded source).
  2. If Wikipedia returns nothing relevant, fall back to the model's own
     training knowledge.
  3. If neither has a reliable identification, emit the `<Not found>`
     sentinel.

This prioritises grounded answers while preserving recall on figures whose
Wikipedia entries are missing, ambiguous, or named differently than the
input.

If the agent's final reply fails to parse as JSON, the parse error is sent
back with a "fix it" instruction, up to `MAX_ATTEMPTS` times. The retry loop
is a safety net for the JSON envelope only — the ladder above is what makes
the content reliable.
"""

from __future__ import annotations

import json
from typing import Any

import wikipedia as _wikipedia
from langchain.agents import create_agent
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.tools import tool
from langchain_groq import ChatGroq

from person_finder.config import groq_api_key

# Wikipedia's robot policy (https://w.wiki/4wJS, Phabricator T400119) rejects
# requests without a descriptive User-Agent — the python-`wikipedia` library's
# default UA gets a 403. Setting one here at import time fixes every call
# `WikipediaAPIWrapper` issues downstream.
_wikipedia.set_user_agent(
    "person_finder/0.1 (NN GenAI assessment; +https://randomuser.me)"
)


SYSTEM_PROMPT = """You are a research assistant identifying people. Wikipedia is your primary
source; your own training knowledge is a fallback.

For each name the user provides, follow this ladder:

1. Call the `wikipedia_search` tool with the name as the query.
2. If the tool returns an article that clearly describes a real public figure
   with that name, write `[source: wiki] ` followed by a 1-2 sentence summary
   covering who they are and their best-known work, drawn from the article.
3. If the tool returns nothing, an unrelated article, or a disambiguation /
   no-match message, fall back to your own training knowledge: if you can
   confidently identify the person yourself, write `[source: llm] ` followed
   by the same 1-2 sentence summary from what you know.
4. Only if Wikipedia returned nothing AND you have no reliable knowledge of
   the person, use the literal string "<Not found>" for `info` (no prefix —
   the sentinel stands alone).

After researching every name, return a single JSON object:

  {"data": [{"person": "First Last", "info": "..."}]}

Rules:
- `person` must match the input name verbatim.
- `info` must be EXACTLY one of: `<Not found>`, a string starting with
  `[source: wiki] `, or a string starting with `[source: llm] ` — no other
  prefix forms (case, spacing, brackets) are valid.
- Do not embellish beyond what your source (Wikipedia, then memory) actually
  supports. Prefer accurate-but-brief over creative.
- If multiple people share a name, pick the most prominent.
- Output ONLY the final JSON object. No prose, no markdown fences.
"""

MAX_ATTEMPTS = 3

_WIKI = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=1500)


@tool
def wikipedia_search(query: str) -> str:
    """Look up a person on Wikipedia and return the top article's summary.

    Use this for every input name to ground identification in factual content.
    Returns the article title + summary on a hit, or an empty/no-match message
    when nothing relevant is found.
    """
    return _WIKI.run(query)


def _model() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=groq_api_key(),
        temperature=0,
    )


def enrich_names(names: list[str], *, model: Any | None = None) -> dict[str, Any]:
    """Ask the LLM to identify each name; re-prompt on JSON parse failure.

    Total LLM invocations are capped at `MAX_ATTEMPTS` (1 initial + up to
    `MAX_ATTEMPTS - 1` repair calls). On final failure raises the last
    `json.JSONDecodeError`.
    """
    agent = create_agent(
        model=model if model is not None else _model(),
        tools=[wikipedia_search],
        system_prompt=SYSTEM_PROMPT,
    )
    messages: list[Any] = [
        {
            "role": "user",
            "content": "Identify these people:\n" + "\n".join(f"- {n}" for n in names),
        }
    ]
    last_error: json.JSONDecodeError | None = None
    for _ in range(MAX_ATTEMPTS):
        result = agent.invoke({"messages": messages})
        raw = result["messages"][-1].content
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            last_error = exc
            messages = list(result["messages"]) + [
                {
                    "role": "user",
                    "content": f"[Invalid JSON] {exc}, fix and return valid JSON only",
                }
            ]
    assert last_error is not None
    raise last_error
