"""Ex5: a LangChain agent that researches a person's most notable work.

Unlike the deterministic identify step in :mod:`person_finder.agent`, this is a
genuine tool-calling agent: it is given the ``wikipedia_lookup`` tool and
*decides* to call it to ground its answer, then reports the person's single
most notable work in 1-2 sentences.

The agent is intentionally narrow — one tool, one job — so it stays cheap and
testable. :func:`research_best_work` accepts an injected ``agent`` so unit
tests can drive the extraction logic with a fake graph and no network.
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_groq import ChatGroq

from person_finder.config import groq_api_key
from person_finder.text import is_unknown
from person_finder.tools import wikipedia_lookup

# A tool-capable model: `create_agent` drives the tool-calling protocol, which
# the smaller 8B instant model emits unreliably. The agent runs at most once
# per identified person (and the run is capped at 5 people), so the larger
# model's cost is bounded.
AGENT_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You research a single real person and report their most \
notable work or achievement.

Always call the wikipedia_lookup tool first to ground your answer in a source.
Then reply with 1-2 sentences naming the one thing this person is most
celebrated for — a book, discovery, invention, role, or body of work.

If the lookup finds no article and you cannot confidently name a real
achievement for this specific person, reply with exactly the single word
UNKNOWN (no other text)."""


def build_best_work_agent(model: Any | None = None) -> Any:
    """Return a compiled tool-calling agent bound to ``wikipedia_lookup``."""
    llm = model if model is not None else ChatGroq(
        model=AGENT_MODEL,
        api_key=groq_api_key(),
        temperature=0,
        # Unlike the user-facing identify step (max_retries=0, fail fast with
        # an actionable message), the agent runs a multi-step tool loop on the
        # 70B model whose free-tier TPM budget is easily throttled. A small
        # retry budget lets it honor Groq's ~2s Retry-After and finish the
        # loop instead of aborting it half-way. Persistent errors still
        # surface to render.py's APIStatusError handler.
        max_retries=3,
    )
    return create_agent(
        llm,
        tools=[wikipedia_lookup],
        system_prompt=SYSTEM_PROMPT,
    )


def tool_was_called(messages: list[Any]) -> bool:
    """True if the agent run actually invoked a tool (a ToolMessage exists).

    The architecture's whole point is "agent calls tools"; this lets the eval
    tier assert the agent grounded its answer rather than answering blind.
    """
    return any(isinstance(m, ToolMessage) for m in messages)


def research_best_work(name: str, *, agent: Any | None = None) -> str | None:
    """Return 1-2 sentences on `name`'s most notable work, or `None`.

    `None` means the agent emitted the UNKNOWN sentinel — it could not name a
    confident achievement for this person.
    """
    agent = agent if agent is not None else build_best_work_agent()
    result = agent.invoke(
        {
            "messages": [
                (
                    "user",
                    f'What is the single most notable work or achievement '
                    f'of "{name}"?',
                )
            ]
        }
    )
    answer = result["messages"][-1].content.strip()
    if is_unknown(answer):
        return None
    return answer
