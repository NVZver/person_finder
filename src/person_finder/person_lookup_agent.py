"""The single person-lookup agent (assignment Ex4 + Ex5).

One LangChain tool-calling agent owns the whole decision tree, grounded in two
tools. Given a name it decides — guided by :data:`SYSTEM_PROMPT` — to:

  1. call ``lookup_person`` to check Wikipedia; identify from the article
     (``source="wiki"``), else from its own knowledge (``source="llm"``), else
     declare the person UNKNOWN;
  2. if identified, call ``lookup_best_work`` and report the single most
     notable work, falling back to its own knowledge, else ``None``.

The agent returns a :class:`PersonResult` via structured output. Each result is
verified against the output contract; a genuine contradiction earns the agent
one repair attempt, after which the result is coerced to a contract-safe shape
so one bad row never aborts the run.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain.agents import create_agent
from pydantic import BaseModel

from person_finder import config
from person_finder.text import is_unknown
from person_finder.tools import lookup_best_work, lookup_person

__all__ = ["PersonResult", "build_person_lookup_agent", "lookup_person_info", "lookup_people"]


class PersonResult(BaseModel):
    """The agent's self-reported, structured answer for one person.

    Contract: ``info`` and ``source`` are paired (both set, or both null);
    ``best_work`` requires identification (null when ``info`` is null).
    """

    info: str | None = None
    source: Literal["wiki", "llm"] | None = None
    best_work: str | None = None


SYSTEM_PROMPT = """You identify a single real person and report their single \
most notable work, grounded in tools.

Work in two steps for the given name:

1. IDENTIFY. First call the `lookup_person` tool to check Wikipedia.
   - If the article clearly describes a specific, real, notable public figure,
     identify them in 1-2 sentences and set source="wiki".
   - If there is no usable article, you may identify them from your own
     knowledge ONLY if you are highly confident they are a genuinely notable
     public figure; then set source="llm".
   - Otherwise the person is UNKNOWN: set info=null, source=null, best_work=null.
     These names come from a random user generator, so MOST belong to ordinary,
     non-famous people — when in doubt, return UNKNOWN.

2. BEST WORK (only if identified). Call the `lookup_best_work` tool and report
   the one thing this person is most celebrated for in 1-2 sentences. Fall back
   to your own knowledge if the tool finds nothing; if you cannot confidently
   name a notable work, set best_work=null.

Return your answer as the structured PersonResult. Never set source or
best_work when info is null."""


def build_person_lookup_agent(model: Any | None = None) -> Any:
    """Return a compiled agent bound to both tools with structured output."""
    return create_agent(
        model if model is not None else config.build_llm(),
        tools=[lookup_person, lookup_best_work],
        system_prompt=SYSTEM_PROMPT,
        response_format=PersonResult,
    )


def _identified(result: PersonResult) -> bool:
    """True when `info` names a real person (not empty / not the UNKNOWN sentinel)."""
    return bool(result.info) and not is_unknown(result.info)


def _verify(result: PersonResult) -> list[str]:
    """Return contract violations worth asking the agent to fix; empty if clean."""
    problems: list[str] = []
    if not _identified(result):
        if result.source is not None:
            problems.append("source must be null when the person is not identified")
        if result.best_work:
            problems.append("best_work must be null when the person is not identified")
    elif result.source not in ("wiki", "llm"):
        problems.append("source must be 'wiki' or 'llm' when info is present")
    return problems


def _coerce(result: PersonResult) -> PersonResult:
    """Normalize to a contract-safe result (last resort after repair)."""
    if not _identified(result):
        return PersonResult(info=None, source=None, best_work=None)
    best = result.best_work if (result.best_work and not is_unknown(result.best_work)) else None
    # Identification is kept; an unusable source defaults to the lower-trust
    # "llm" so the (info, source) pair stays valid rather than dropping recall.
    source = result.source if result.source in ("wiki", "llm") else "llm"
    return PersonResult(info=result.info, source=source, best_work=best)


def _user_prompt(name: str) -> str:
    return (
        f'Identify the person named "{name}". '
        "If identified, find their single most notable work."
    )


def _invoke(agent: Any, name: str, *, repair: list[str] | None = None) -> PersonResult | None:
    """Run the agent once. Returns the structured result, or `None` when the
    agent ended without producing one (e.g. it emitted duplicate structured
    calls and langchain set no `structured_response`)."""
    messages: list[tuple[str, str]] = [("user", _user_prompt(name))]
    if repair:
        messages.append(
            (
                "user",
                "Your previous answer was invalid: "
                + "; ".join(repair)
                + ". Return corrected structured output.",
            )
        )
    result = agent.invoke({"messages": messages})
    return result.get("structured_response")


def _problems(result: PersonResult | None) -> list[str]:
    if result is None:
        return ["no structured output was returned"]
    return _verify(result)


def lookup_person_info(name: str, *, agent: Any) -> PersonResult:
    """Identify `name` and research their best work, verified and contract-safe.

    A missing or contract-violating result earns the agent one repair attempt;
    the result is then coerced (or nulled) so callers always receive a valid
    `PersonResult`.
    """
    result = _invoke(agent, name)
    problems = _problems(result)
    if problems:
        result = _invoke(agent, name, repair=problems)
    if result is None:
        return PersonResult()
    return _coerce(result)


def lookup_people(names: list[str], *, agent: Any | None = None) -> dict[str, Any]:
    """Run the agent over each name and return ``{"data": [{person, info, source, best_work}]}``.

    The agent is built once and reused across names. `agent` is injectable so
    tests run fully offline.
    """
    agent = agent if agent is not None else build_person_lookup_agent()
    rows: list[dict[str, Any]] = []
    for name in names:
        result = lookup_person_info(name, agent=agent)
        rows.append(
            {
                "person": name,
                "info": result.info,
                "source": result.source,
                "best_work": result.best_work,
            }
        )
    return {"data": rows}
