"""LangChain ReAct agent that maps a list of names to a JSON-shaped enrichment string."""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_groq import ChatGroq

from person_finder.config import get_settings


SYSTEM_PROMPT = """You are a research assistant.

For each person name the user provides, call the `findPerson` tool exactly once
to look up publicly available information about that person, then return a
single JSON object matching this schema:

  {"data": [{"person": "First Last", "info": "..."}]}

Rules:
- `person` must match the input name verbatim.
- `info` is a non-empty string summarizing what you found, OR the literal
  string "<Not found>" when the tool returns nothing useful.
- Output ONLY the JSON object. No prose, no markdown fences.
"""


@tool
def findPerson(name: str) -> str:  # noqa: N802 — name fixed by cross-module contract
    """Look up publicly available information about a person by full name.

    Returns a short factual summary or the literal string ``"<Not found>"``.
    """
    return "<Not found>"


def _default_model() -> ChatGroq:
    # Pull the key via Settings (not ChatGroq's ambient os.environ lookup) so a
    # missing/blank GROQ_API_KEY fails at construction, not deep in an HTTP retry.
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=get_settings().groq_api_key,
        temperature=0,
    )


def build_agent(model: Any | None = None):
    return create_agent(
        model=model if model is not None else _default_model(),
        tools=[findPerson],
        system_prompt=SYSTEM_PROMPT,
    )


def enrich_names(names: list[str], *, model: Any | None = None) -> str:
    agent = build_agent(model=model)
    user_msg = "Look up information for these people:\n" + "\n".join(
        f"- {n}" for n in names
    )
    result = agent.invoke({"messages": [{"role": "user", "content": user_msg}]})
    return result["messages"][-1].content


REPAIR_SYSTEM_PROMPT = """You previously produced output that failed schema validation.

Required schema: {"data": [{"person": str, "info": str}]}.

Return ONLY a corrected JSON object matching that schema. No prose, no markdown
fences. Do not invent new people; preserve the original `person` values.
"""


def repair(broken_raw: str, error_msg: str, *, model: Any | None = None) -> str:
    """One-shot LLM repair pass over a validation-failed JSON candidate.

    Wraps the cross-module repair callable contract from
    [validation/spec.md F4](../../specs/modules/validation/spec.md):
    ``(broken_raw, error_msg) -> repaired_raw``. The fix is a single model
    call (no ReAct loop / no tool calls) because repair is targeted JSON
    surgery, not enrichment.

    Constructed lazily — the default model is built per call via
    :func:`_default_model` so ``import person_finder.agent`` stays
    side-effect-free (NF2).
    """
    llm = model if model is not None else _default_model()
    user_msg = (
        f"Previous output failed validation: {error_msg}\n\n"
        f"Broken output was:\n{broken_raw}\n\n"
        "Return a corrected JSON object only."
    )
    response = llm.invoke(
        [
            {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
    )
    return response.content
