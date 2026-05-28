"""LangChain agent that turns a list of names into a parsed JSON dict.

The agent answers from the LLM's own training knowledge (no external tools),
matching the assignment's Exercises 4-5. If the model's reply fails to parse
as JSON, the parse error is sent back to the model with a "fix it" instruction,
up to MAX_RETRIES times.
"""

from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent
from langchain_groq import ChatGroq

from person_finder.config import Settings


SYSTEM_PROMPT = """You are a research assistant identifying people from your training knowledge.

For each person name the user provides, return a single JSON object with this schema:

  {"data": [{"person": "First Last", "info": "..."}]}

Rules:
- `person` must match the input name verbatim.
- `info` is a short factual summary (1-2 sentences) covering who the person is and
  their best-known work, drawn from your training knowledge.
- If you genuinely don't recognize the name (e.g. a random private individual),
  set `info` to the literal string "<Not found>".
- Output ONLY the JSON object. No prose, no markdown fences.
"""

MAX_RETRIES = 3


def _model() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=Settings().groq_api_key,
        temperature=0,
    )


def enrich_names(names: list[str], *, model: Any | None = None) -> dict[str, Any]:
    """Ask the LLM to identify each name; re-prompt on JSON parse failure.

    Returns the parsed JSON dict. After MAX_RETRIES failed parses, raises the
    final `json.JSONDecodeError`.
    """
    agent = create_agent(
        model=model if model is not None else _model(),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )
    messages: list[Any] = [
        {
            "role": "user",
            "content": "Identify these people:\n" + "\n".join(f"- {n}" for n in names),
        }
    ]
    last_error: json.JSONDecodeError | None = None
    for _ in range(MAX_RETRIES + 1):
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
