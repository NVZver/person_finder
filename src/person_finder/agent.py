"""LangChain agent that turns a list of names into a JSON enrichment string.

The agent answers from the LLM's own training knowledge (no external tools),
matching the assignment's Exercises 4-5. A separate `repair` callable is
exposed for the validation layer's retry loop.
"""

from __future__ import annotations

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

REPAIR_SYSTEM_PROMPT = """You previously produced output that failed schema validation.

Required schema: {"data": [{"person": str, "info": str}]}.

Return ONLY a corrected JSON object matching that schema. No prose, no markdown
fences. Do not invent new people; preserve the original `person` values.
"""


def _model() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=Settings().groq_api_key,
        temperature=0,
    )


def enrich_names(names: list[str], *, model: Any | None = None) -> str:
    agent = create_agent(
        model=model if model is not None else _model(),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )
    user_msg = "Identify these people:\n" + "\n".join(f"- {n}" for n in names)
    result = agent.invoke({"messages": [{"role": "user", "content": user_msg}]})
    return result["messages"][-1].content


def repair(broken_raw: str, error_msg: str, *, model: Any | None = None) -> str:
    """One-shot LLM repair pass for the validation layer's retry loop."""
    llm = model if model is not None else _model()
    response = llm.invoke(
        [
            {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Previous output failed validation: {error_msg}\n\n"
                    f"Broken output was:\n{broken_raw}\n\n"
                    "Return a corrected JSON object only."
                ),
            },
        ]
    )
    return response.content
