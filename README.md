# person_finder

A small Python CLI that fetches 20 random users from
[randomuser.me](https://randomuser.me), filters out anyone born after
the year 2000, asks a LangChain ReAct agent (running on Groq's
`llama-3.3-70b-versatile`) to look up publicly-available information for
each remaining person, validates the agent's JSON output (with a
3-attempt repair loop), and prints the result to stdout.

## Pipeline

```
randomuser.me  ->  filter by DOB year  ->  LangChain ReAct agent (Groq)
                                              |
                                              v
                              validate JSON  +  repair-retry loop
                                              |
                                              v
                              stdout:  {"data": [{"person": "...", "info": "..."}]}
```

On success the process exits `0`. On either `users.UserFetchError`
(upstream failure) or `validation.Error` (repair budget exhausted) it
prints `Could not respond — please try again later.` to stderr and exits
non-zero (no traceback leaked to the user).

## Requirements

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/) for dependency + venv management
- A [Groq API key](https://console.groq.com)
- A [Google AI Studio API key](https://aistudio.google.com) (required by
  the config layer; consumed by the DeepEval Gemini judge in the eval
  suite)

## Setup

```bash
# Install dependencies into a local .venv
make sync           # or:  uv sync

# Provide the API keys
cp .env.example .env
# then edit .env and fill in GROQ_API_KEY + GOOGLE_API_KEY
```

## Run

```bash
uv run python -m person_finder
```

Expected output:

```json
{
  "data": [
    {"person": "Adam Smith", "info": "..."},
    {"person": "Cara Lopez", "info": "<Not found>"}
  ]
}
```

## Tests

Three tiers, each runnable on its own:

```bash
make test-unit      # fast, fully mocked — no network, no LLM
make test-eval      # DeepEval metrics over the live agent output
make test-e2e       # full pipeline against real randomuser.me + Groq
make test-all       # all three in order
```

`test-eval` and `test-e2e` skip cleanly when their required API keys are
absent, so they stay green in dev environments without credentials.
