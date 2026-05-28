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


SYSTEM_PROMPT = """Identify people. Wikipedia first, training knowledge as fallback.

For each input name:
1. Call `wikipedia_search` with the name.
2. If the article clearly describes a real public figure of that name, return
   `[source: wiki] ` + a 1-2 sentence summary drawn from the article.
3. Else, if you confidently know the person, return `[source: llm] ` + a 1-2
   sentence summary from training knowledge.
4. Only if Wikipedia AND training knowledge both fail, use `<Not found>`.

Return ONE JSON object: {"data": [{"person": "First Last", "info": "..."}]}

- `person` matches the input verbatim.
- `info` is EXACTLY one of: `<Not found>`, `[source: wiki] ...`, `[source: llm] ...`.
- Don't embellish beyond the source. On name clashes, pick the most prominent.
- Output ONLY the JSON. No prose, no markdown fences.
"""

MAX_ATTEMPTS = 3

_WIKI = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=600)


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
        model="llama-3.1-8b-instant",
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
            # Repair retry: drop the tool transcript — only the syntax needs
            # fixing, and replaying every wikipedia_search result is wasted
            # tokens. The system prompt is still applied by the agent.
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"The previous output was not valid JSON ({exc}). "
                        "Return ONLY a valid JSON object matching the schema. "
                        "Do not call tools.\n\n"
                        f"Previous output:\n{raw}"
                    ),
                }
            ]
    assert last_error is not None
    raise last_error
