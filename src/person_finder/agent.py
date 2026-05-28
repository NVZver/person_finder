"""LangChain agent that maps a list of names to a JSON-shaped enrichment string.

The agent answers from the LLM's own training knowledge — there is no
external lookup tool. The assignment (Exercises 4-5) explicitly asks the
LLM itself to identify the person and describe their best-known work; the
bonus anticipates that not every random user from `randomuser.me` will be
recognizable. The "agentic" framing is preserved by going through
`create_agent` (with an empty tool list) so the same runtime surface is
available for adding real tools later without changing the call site.
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain_groq import ChatGroq

from person_finder.config import get_settings


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
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )


def enrich_names(names: list[str], *, model: Any | None = None) -> str:
    agent = build_agent(model=model)
    user_msg = "Identify these people:\n" + "\n".join(f"- {n}" for n in names)
    result = agent.invoke({"messages": [{"role": "user", "content": user_msg}]})
    return result["messages"][-1].content


REPAIR_SYSTEM_PROMPT = """You previously produced output that failed schema validation.

Required schema: {"data": [{"person": str, "info": str}]}.

Return ONLY a corrected JSON object matching that schema. No prose, no markdown
fences. Do not invent new people; preserve the original `person` values.
"""


def repair(broken_raw: str, error_msg: str, *, model: Any | None = None) -> str:
    """One-shot LLM repair pass over a validation-failed JSON candidate.

    Implements the ``(broken_raw, error_msg) -> repaired_raw`` callable
    contract consumed by :func:`person_finder.validation.validate_output`.
    The fix is a single model call (no agent loop) because repair is
    targeted JSON surgery, not enrichment.

    Constructed lazily — the default model is built per call via
    :func:`_default_model` so ``import person_finder.agent`` stays
    side-effect-free.
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
