"""Identify each name via a Groq LLM, using its own training knowledge.

The model returns raw JSON in the agreed shape; if a reply fails to parse,
the parse error is sent back to the model with a "fix it" instruction, up
to MAX_ATTEMPTS times. We use `create_agent(tools=[])` to keep the surface
on the LangChain agent path even though no tools are wired — matching the
assignment's "agentic workflow using LangChain" framing.
"""

from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent
from langchain_groq import ChatGroq

from person_finder.config import groq_api_key


SYSTEM_PROMPT = """You are a research assistant identifying people using your own training knowledge.

For each person name the user provides, return a single JSON object with this schema:

  {"data": [{"person": "First Last", "info": "..."}]}

Rules:
- `person` must match the input name verbatim.
- `info` is a 1-2 sentence factual summary of who the person is and their best-known
  work, drawn from your training knowledge.
- Default to providing a summary whenever the name plausibly matches a real public
  figure you know — historical, scientific, cultural, political, athletic, business,
  or otherwise. If several people share the name, pick the most prominent.
- Use the literal string "<Not found>" ONLY when the name is clearly a random
  private individual you have no knowledge of — never as a fallback for ambiguity.
- Output ONLY the JSON object. No prose, no markdown fences.
"""

MAX_ATTEMPTS = 3


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
