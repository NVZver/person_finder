# person_finder

A Python CLI that fetches random users from [randomuser.me](https://randomuser.me),
keeps those born on or before 2000 (capped at 5), and for each name runs two
stages:

- **identify** — Wikipedia first, Groq-hosted `llama-3.3-70b-versatile` as
  fallback. Each row is tagged `source: "wiki" | "llm" | null`.
- **best work** — a LangChain tool-calling agent that researches each
  identified person's most notable achievement.

The result is printed to stdout as JSON. Unidentified people get
`info`, `source`, and `best_work` all `null`.

```json
{
  "data": [
    {"person": "Adam Smith", "info": "Scottish economist and moral philosopher (1723-1790).", "source": "wiki", "best_work": "The Wealth of Nations (1776)."},
    {"person": "Cara Lopez", "info": null, "source": null, "best_work": null}
  ]
}
```

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
