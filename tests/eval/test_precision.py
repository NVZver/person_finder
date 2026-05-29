"""Live precision guard: fictional names must NOT be hallucinated.

The recall guard (`NoNullInfo` over `PUBLIC_FIGURES` in `test_live_agent.py`)
proves the pipeline identifies people it *should*. This is the mirror: it
proves the pipeline stays (mostly) silent on people it *cannot* know.

`FICTIONAL_NAMES` are mundane, randomuser-style names of non-famous people.
For every one, the correct output is the null pair (`info`/`source` null) —
a populated `info` means the identify step invented a biography, the exact
failure a person-identification tool for a regulated insurer must not make.

History: on `llama-3.1-8b-instant` this guard failed 4/4 — the 8B model
fabricated a confident biography for every fictional name. The identify step
was moved to `llama-3.3-70b-versatile`, which refuses far more reliably but is
not perfect. So the guard is a *rate* with a high floor: it catches the
systematic 8B-style failure without flaking on an occasional 70B slip. The
ideal is zero leaks; the threshold documents the residual risk that 70B
sometimes still guesses.

The check is deterministic (no LLM judge) and runs identify-only (no 70B
agent), so it stays cheap. Skips cleanly without `GROQ_API_KEY`.
"""

from __future__ import annotations

# At most this fraction of clearly-fictional names may slip through as a
# hallucinated identification. 0.75 over a 4-name roster tolerates one 70B
# slip while still failing the systematic, every-name fabrication that the 8B
# model produced.
_MIN_NULL_RATE = 0.75


def test_fictional_names_are_rarely_hallucinated(live_fictional_payload: dict) -> None:
    rows = live_fictional_payload["data"]

    leaked = [r for r in rows if r["info"] is not None]
    null_rate = 1 - len(leaked) / len(rows)

    assert null_rate >= _MIN_NULL_RATE, (
        f"identify step hallucinated for {len(leaked)}/{len(rows)} fictional "
        f"names (null rate {null_rate:.0%} < required {_MIN_NULL_RATE:.0%}). "
        f"It must return UNKNOWN for people it cannot know:\n"
        + "\n".join(
            f"  - {r['person']!r} -> info={r['info']!r} (source={r['source']})"
            for r in leaked
        )
    )

    # info null implies source null by the paired-null contract.
    for r in rows:
        if r["info"] is None:
            assert r["source"] is None
