# person_finder

A Python CLI that fetches random users from [randomuser.me](https://randomuser.me),
keeps those born on or before 2000 (capped at 5), and hands each name to a
single LangChain agent (Groq-hosted `llama-3.3-70b-versatile`) with two tools:

- **`lookup_person`** — Wikipedia bio lookup for *who the person is*.
- **`lookup_best_work`** — Wikipedia lookup for their *most notable work*.

The agent decides for itself: identify from Wikipedia (`source: "wiki"`), else
from its own knowledge (`source: "llm"`), else `UNKNOWN`; and only then research
the best work. Its structured output is verified against the contract, with one
self-repair attempt before a contract-safe fallback.

The result is printed to stdout as JSON (the formatted names array is logged to
stderr). Unidentified people get `info`, `source`, and `best_work` all `null`.

```json
{
  "data": [
    {"person": "Adam Smith", "info": "Scottish economist and moral philosopher (1723-1790).", "source": "wiki", "best_work": "The Wealth of Nations (1776)."},
    {"person": "Cara Lopez", "info": null, "source": null, "best_work": null}
  ]
}
```

## Architecture

C4 model docs (high-level, top-down):

- [L1 — System Context](docs/c4-1-context.md)
- [L2 — Container](docs/c4-2-container.md)
- [L3 — Component](docs/c4-3-component.md)
- [L4 — Code](docs/c4-4-code.md) — the Person Lookup Agent internals

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- A [Groq API key](https://console.groq.com)

## Setup

```bash
make sync                 # install deps into .venv (or: uv sync)
cp .env.example .env       # then fill in GROQ_API_KEY
```

## Run

```bash
uv run python -m person_finder
```

## Test

```bash
make test-unit            # fast, fully mocked — no network, no LLM
make test-eval            # DeepEval over one live run: structural + semantic
make test-e2e             # full pipeline against real randomuser.me + Groq
make test-all             # all three in order
```

`test-eval` and `test-e2e` skip cleanly when `GROQ_API_KEY` is absent.
