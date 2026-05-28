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

## Design choices

A few decisions worth calling out:

- **Single batched LLM call, not one-per-name.** Twenty names go in one
  prompt; one structured response comes back. Per-name calls would multiply
  the system-prompt overhead 20× for identical work.
- **`temperature=0`.** Identical input → identical output. Required for the
  deterministic eval metrics in `tests/eval/` to function as a meaningful
  regression guard.
- **"Filter out people born after 2000" → `year <= 2000`.** The phrasing is
  ambiguous ("filter out" reads both ways); I chose the exclude-post-2000
  interpretation and keep year 2000 itself as the boundary case (pinned by
  `test_boundary_year_2000_is_kept`).
- **`<Not found>` sentinel string, not empty string or null.** Empty
  collides with "model returned nothing"; null forces every consumer to
  handle the optional. A documented sentinel prints cleanly in JSON and is
  grep-friendly.
- **Refuse to hallucinate.** The prompt biases toward identifying
  plausibly-real names but explicitly restricts `<Not found>` to clearly
  random private individuals. Trade-off chosen deliberately: for a regulated
  insurer, a fabricated biography is a worse failure than an honest empty.
  Most `randomuser.me` rows correctly come back as `<Not found>` because the
  names are fictional; iconic public figures are identified reliably (pinned
  by `tests/eval/test_live_agent.py`).
- **CLI surface, not HTTP.** Scope-appropriate. `enrich_names()` is a pure
  function and would wrap into a FastAPI endpoint in ~30 lines if production
  needed it.

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

- **Latency.** Measured over 5 runs: median **1.07s** end-to-end
  (range 0.86–2.36s). Breakdown: randomuser.me HTTP ~0.16s, Groq LLM
  ~0.89s. The repair-retry loop is bounded at `MAX_ATTEMPTS = 3` so the
  hard ceiling is 3× the LLM call.
- **Cost.** Measured median ~**353 input + ~379 output tokens** per run.
  At Groq's published rates for `llama-3.3-70b-versatile` ($0.59/M input,
  $0.79/M output) that works out to ~**$0.0005 per run** — roughly half
  a cent per ten runs. Single batched call (not per-name) keeps the
  system-prompt overhead amortized.
- **Reliability.** Failures are typed at the boundary (`UserFetchError`,
  `json.JSONDecodeError`) and translated into a single user-facing message
  with a non-zero exit code; no internal traceback reaches the user.
