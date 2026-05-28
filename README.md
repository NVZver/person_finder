# person_finder

A small Python CLI for the NN GenAI Engineer assignment. It fetches 20 random
users from [randomuser.me](https://randomuser.me), filters out anyone born
after the year 2000, asks a Groq-hosted `llama-3.3-70b-versatile` model to
identify each remaining person from its training knowledge, validates the
returned JSON (with a bounded repair-retry loop), and prints the result to
stdout.

## Pipeline

```
randomuser.me  ->  filter by DOB year  ->  Groq llama-3.3-70b
                                              |
                                              v
                              validate JSON  +  repair-retry loop
                                              |
                                              v
                              stdout:  {"data": [{"person": "...", "info": "..."}]}
```

On success the process exits `0`. On either `users.UserFetchError` (upstream
failure) or a final `json.JSONDecodeError` (repair budget exhausted) it prints
`Could not respond — please try again later.` to stderr and exits non-zero —
no traceback leaked to the user.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency + venv management
- A [Groq API key](https://console.groq.com)

## Setup

```bash
# Install dependencies into a local .venv
make sync           # or:  uv sync

# Provide the API key
cp .env.example .env
# then edit .env and fill in GROQ_API_KEY
```

No other keys are required.

## Run

```bash
uv run python -m person_finder
```

Example output (names will vary — `randomuser.me` returns fictional people, so
most `info` fields will be `<Not found>`):

```json
{
  "data": [
    {"person": "Adam Smith", "info": "<Not found>"},
    {"person": "Cara Lopez", "info": "<Not found>"}
  ]
}
```

## Tests

Three tiers, each runnable on its own:

```bash
make test-unit      # fast, fully mocked — no network, no LLM
make test-eval      # DeepEval deterministic metrics over live agent output
make test-e2e       # full pipeline against real randomuser.me + Groq
make test-all       # all three in order
```

`test-eval` and `test-e2e` skip cleanly when their required API keys are
absent, so they stay green in dev environments without credentials.

## Engineering notes

A few production-shaped choices, called out because the role asks for them:

- **Latency.** Groq + Llama-3.3-70B chosen for sub-second TTFT on small
  prompts. The repair loop is bounded at `MAX_ATTEMPTS = 3` so worst-case
  latency stays predictable.
- **Cost.** All `N` names are enriched in a single LLM call (batched, not
  per-name) to amortize the system-prompt cost. `temperature=0` keeps output
  reproducible.
- **Reliability.** Failures are typed at the boundary (`UserFetchError`,
  `json.JSONDecodeError`) and translated into a single user-facing message
  with a non-zero exit code; no internal traceback reaches the user.
