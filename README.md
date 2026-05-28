# person_finder

A small Python CLI for the NN GenAI Engineer assignment. It fetches 20 random
users from [randomuser.me](https://randomuser.me), filters out anyone born
after the year 2000, then runs a per-name pipeline — Wikipedia first,
Groq-hosted `llama-3.1-8b-instant` as fallback — that identifies each
remaining person and tags the source of the answer. The resulting JSON is
printed to stdout.

## Pipeline

```
randomuser.me  ->  filter by DOB year  ->  per-name loop:
                                             |
                                             v
                                   wikipedia.summary(name)
                                             |
                                  hit -> llm.invoke(summarize)  --> source = "wiki"
                                  miss -> llm.invoke(identify)
                                             |
                                  reply: "UNKNOWN"  -> info=null, source=null
                                  reply: summary    -> source = "llm"
                                             |
                                             v
                              stdout: {"data": [{"person": "...", "info": "...", "source": "wiki"}]}
```

On success the process exits `0`. On `users.UserFetchError` (upstream failure)
it prints `Could not respond — please try again later.` to stderr and exits
non-zero. On a Groq API error (rate limit, context length, auth, 5xx) it
prints `Error: <Groq's actionable message>` (e.g. `"… Please try again in
2.1s"`) and exits non-zero. No traceback ever reaches the user.

## Design choices

A few decisions worth calling out:

- **Per-name deterministic pipeline, not a tool-using agent.** For each
  name we call `wikipedia.summary()` directly. On a hit, the LLM is asked
  to compress the article to 1-2 sentences (`source="wiki"`). On a miss,
  the LLM is asked to identify the person from training knowledge —
  responding either with a summary (`source="llm"`) or the literal
  `UNKNOWN` (`source=null`, `info=null`). The LLM never decides the
  `source` field or whether `info` is null — those are derived from
  which retrieval step succeeded. This eliminates an entire class of
  failure modes (LLM emits the string `"null"` instead of JSON `null`;
  LLM forgets the source tag; LLM nests tool calls in text format on
  smaller models).
- **`temperature=0`.** Identical input → identical output. Required for the
  deterministic eval metrics in `tests/eval/` to function as a meaningful
  regression guard.
- **`max_retries=0` on the Groq client.** The SDK's default 2-retries-with-
  backoff means a 429 hangs silently for ~30s before raising. Setting to
  zero surfaces the error immediately, so the CLI can print Groq's
  actionable "try again in Ns" message and exit fast.
- **"Filter out people born after 2000" → `year <= 2000`.** The phrasing is
  ambiguous ("filter out" reads both ways); I chose the exclude-post-2000
  interpretation and keep year 2000 itself as the boundary case (pinned by
  `test_boundary_year_2000_is_kept`).
- **Structured `source` field with paired-null `info`.** Each row carries
  `info: str | null` and `source: "wiki" | "llm" | null` — paired (both
  populated or both null) by construction. Consumers can branch on
  `source` directly without parsing magic strings out of `info`.
- **Refuse to hallucinate.** The identify prompt instructs the LLM to
  emit `UNKNOWN` when it cannot confidently identify a specific real
  person with the given name. We map that to the null pair. Trade-off
  chosen deliberately: for a regulated insurer, a fabricated biography is
  a worse failure than an honest empty. Most `randomuser.me` rows come
  back as `info: null, source: null` because the names are fictional;
  iconic public figures are identified reliably (pinned by
  `tests/eval/test_live_agent.py`).
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
most rows will be `info: null, source: null`):

```json
{
  "data": [
    {"person": "Adam Smith", "info": "Scottish economist and moral philosopher (1723-1790), best known for The Wealth of Nations.", "source": "wiki"},
    {"person": "Cara Lopez", "info": null, "source": null}
  ]
}
```

The `source` field tags which step of the fallback ladder produced the
summary — `"wiki"` for the Wikipedia article, `"llm"` for the model's
training knowledge. When neither source identifies the person, both `info`
and `source` are `null` (always paired).

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

- **Latency.** Latency scales linearly with the number of filtered names —
  each gets a Wikipedia call and 1-2 small LLM calls. Wikipedia hits are
  cheaper (one LLM call, no fallback); fictional names from
  `randomuser.me` cost two (identify → `UNKNOWN`).
- **Cost.** Each LLM call is small (~150-400 tokens) because the prompts
  are one-shot — no JSON envelope to construct, no tool schemas to bind,
  no agent state to replay. The 8B model is ~10× cheaper per token than
  70B at Groq's published rates. Wikipedia content is capped at 600 chars
  per call to keep the summarize prompt tight.
- **Reliability.** Failures are typed at the boundary and translated into a
  single user-facing message with a non-zero exit code; no traceback
  reaches the user. `UserFetchError` (randomuser.me) prints a generic
  retry message; `groq.APIStatusError` (rate limit, context length, auth,
  5xx) prints Groq's own actionable message extracted from the response
  body.
