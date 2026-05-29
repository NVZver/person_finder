"""A LangChain tool-calling agent that researches a person's most notable work.

Given the ``wikipedia_lookup`` tool, the agent grounds its answer in the
article and reports the person's single most notable work in 1-2 sentences.
:func:`research_best_work` accepts an injected ``agent`` so tests can run it
offline.
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_groq import ChatGroq

from person_finder.config import groq_api_key
from person_finder.text import is_unknown
from person_finder.tools import wikipedia_lookup

# Tool-capable model: the 8B instant model emits tool calls unreliably.
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
        # Honor Groq's short Retry-After so the multi-step tool loop rides out
        # transient throttling instead of aborting half-way.
        max_retries=3,
    )
    return create_agent(
        llm,
        tools=[wikipedia_lookup],
        system_prompt=SYSTEM_PROMPT,
    )


def tool_was_called(messages: list[Any]) -> bool:
    """True if the agent run invoked a tool (a ToolMessage exists)."""
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
