# person_finder

A small Python CLI for the NN GenAI Engineer assignment. It fetches 20 random
users from [randomuser.me](https://randomuser.me), filters out anyone born
after the year 2000, caps the list at 5 people (free-tier rate limits), then
per name runs two stages: **identify** (Ex4 — Wikipedia first, Groq-hosted
`llama-3.3-70b-versatile` as fallback, source-tagged) and **best work** (Ex5 —
a LangChain tool-calling agent that researches each identified person's most
notable achievement). The resulting JSON is printed to stdout.

## Pipeline

```
randomuser.me  ->  filter by DOB year  ->  cap at 5  ->  per-name loop:
                                                           |
            Ex4 identify (deterministic) ─────────────────┤
                                                           v
                                                 wikipedia.summary(name)
                                                           |
                                hit -> llm.invoke(summarize)  --> source = "wiki"
                                miss -> llm.invoke(identify)
                                           |
                                reply: "UNKNOWN"  -> info=null, source=null  (skip Ex5)
                                reply: summary    -> source = "llm"
                                                           |
            Ex5 best work (agentic, identified only) ──────┤
                                                           v
                              create_agent(llm, tools=[wikipedia_lookup])
                                  agent decides to call the tool, then
                                  answers "best work" in 1-2 sentences
                                  (or UNKNOWN -> best_work=null)
                                                           |
                                                           v
        stdout: {"data": [{"person", "info", "source", "best_work"}]}
```

On success the process exits `0`. On `users.UserFetchError` (upstream failure)
it prints `Could not respond — please try again later.` to stderr and exits
non-zero. On a Groq API error (rate limit, context length, auth, 5xx) it
prints `Error: <Groq's actionable message>` (e.g. `"… Please try again in
2.1s"`) and exits non-zero. No traceback ever reaches the user.

## Design choices

A few decisions worth calling out:

- **Deterministic identify step (Ex4), tool-calling agent for best work
  (Ex5).** The two stages have opposite needs, so they use opposite
  designs:
  - *Identify* is **schema-critical** — its output drives the `source`
    field and the paired-null contract — so it is a deterministic
    per-name pipeline. We call `wikipedia.summary()` directly; on a hit
    the LLM compresses the article (`source="wiki"`), on a miss it
    identifies from training knowledge (`source="llm"`) or emits the
    literal `UNKNOWN` (`source=null`, `info=null`). The LLM never decides
    `source` or nullability — those are derived from which retrieval step
    succeeded. This kills a whole class of failure modes (LLM emits the
    string `"null"`; LLM forgets the source tag; small models nest tool
    calls in text format).
  - *Best work* is **research, not schema** — deciding what to look up to
    surface a person's notable achievement is exactly what tool-use is
    for — so it is a genuine `create_agent` agent bound to a
    `wikipedia_lookup` tool. It runs on the tool-capable
    `llama-3.3-70b-versatile` (the 8B instant model emits tool calls
    unreliably), only for already-identified people, and only ≤5 of them.
    Its output is one free-text field (`best_work`); if it gets the field
    wrong the contract still holds. That containment is what lets the
    agent be "agentic" without the reliability cost landing on the schema.
- **`temperature=0`.** Identical input → identical output. Required for the
  deterministic eval metrics in `tests/eval/` to function as a meaningful
  regression guard.
- **`llama-3.3-70b-versatile` for identify, not the 8B instant model.** The
  precision guard (`tests/eval/test_precision.py`) caught the 8B model
  fabricating a confident biography for **4 of 4** clearly-fictional names —
  a German actress, a French racing driver, a Danish health minister, all
  invented. Prompt hardening didn't fix it; the 8B model simply guesses. 70B
  refuses reliably (verified: the same four names return `UNKNOWN`). The cost
  is bounded by the 5-person cap. This is the assignment's thesis in action —
  the test, not the prose, is what makes the "refuse to hallucinate" claim
  true.
- **`max_retries=2` on the Groq client.** The SDK default (2 retries with
  long backoff) can hang ~30s before raising; `0` surfaces errors instantly
  but aborts on any transient throttle. `2` is the middle path: it honors
  Groq's short `Retry-After` (~2s) so the rate-limited 70B model rides out a
  transient TPM throttle, while a persistent error still surfaces fast to the
  CLI's actionable-message handler. The best-work agent and the eval judge use
  `3` for the same reason.
- **"Filter out people born after 2000" → `year <= 2000`.** The phrasing is
  ambiguous ("filter out" reads both ways); I chose the exclude-post-2000
  interpretation and keep year 2000 itself as the boundary case (pinned by
  `test_boundary_year_2000_is_kept`).
- **Cap at 5 people (`MAX_PEOPLE`).** The assignment asks us to stick to 5 to
  stay under free-tier rate limits. `fetch_user_names()` truncates the
  year-filtered list to 5; the cap is a `limit` parameter so tests and future
  callers can change it. With the Ex5 agent each identified person costs
  several model round-trips, so the cap matters more than before.
- **Structured `source` field with paired-null `info`.** Each row carries
  `info: str | null` and `source: "wiki" | "llm" | null` — paired (both
  populated or both null) by construction. Consumers can branch on
  `source` directly without parsing magic strings out of `info`.
- **Refuse to hallucinate — and prove it both ways.** The identify prompt
  instructs the LLM to emit `UNKNOWN` when it cannot confidently identify a
  specific real person; we map that to the null pair. For a regulated
  insurer, a fabricated biography is a worse failure than an honest empty.
  Two live guards pin the trade-off from both sides: `NoNullInfo` over
  `PUBLIC_FIGURES` (recall — iconic figures *must* be identified) and
  `test_precision.py` over `FICTIONAL_NAMES` (precision — fabricated people
  *must* return null). A wiki article that turns out not to be about an
  identifiable person (auto-suggest landing on a disambiguation page) also
  routes to null, and does **not** fall through to the memory path — if
  Wikipedia has no clean match, the model's training memory won't do better,
  it will only guess.
- **Sequential per-name calls, considered and kept.** Each name costs an
  identify call plus (when identified) an agent run; with the 5-cap that is
  a bounded handful of round-trips. Async parallelism over them is the
  cleanest latency win (no token or reliability cost) but adds a concurrency
  surface (async client, error aggregation, ordering) the assignment doesn't
  justify — worth picking up if latency becomes the production constraint.
  Keeping the identify call one-shot text-in/text-out is what keeps the
  output schema fully Python-controlled.
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
    {"person": "Adam Smith", "info": "Scottish economist and moral philosopher (1723-1790).", "source": "wiki", "best_work": "The Wealth of Nations (1776), the foundational text of modern economics."},
    {"person": "Cara Lopez", "info": null, "source": null, "best_work": null}
  ]
}
```

The `source` field tags which step of the identify ladder produced `info` —
`"wiki"` for the Wikipedia article, `"llm"` for the model's training
knowledge. `best_work` is the agent's research (Ex5) on that person's most
notable achievement. When the person isn't identified, `info`, `source`, and
`best_work` are all `null`; an identified person whose notable work the agent
can't confirm keeps `info`/`source` but carries `best_work: null`.

## Tests

Three tiers, each runnable on its own:

```bash
make test-unit      # fast, fully mocked — no network, no LLM
make test-eval      # DeepEval over one live run: structural + semantic metrics
make test-e2e       # full pipeline against real randomuser.me + Groq
make test-all       # all three in order
```

The eval tier itself has two layers, both over a single session-scoped live
run (the agent is expensive and rate-limited, so it runs once):

- **Structural metrics** (`test_live_agent.py`, `metrics.py`) — deterministic,
  pure-Python checks of shape: valid JSON, every `person` in the input,
  paired `info`/`source` nullability, `best_work` only when identified, and
  no-null-info on a known-famous roster. `test_metric_failure_modes.py` tests
  the metrics themselves — proving each *rejects* a violating payload with a
  named reason, not just accepts a good one.
- **Semantic correctness** (`test_correctness.py`, `judge.py`) — an
  LLM-as-judge (`GEval` over a Groq judge) scoring whether `info` and
  `best_work` are *factually true*, not merely well-shaped. A confidently
  wrong biography passes every structural check; this layer is what catches
  it. Covers both the wiki and llm identify paths.
- **Precision guard** (`test_precision.py`) — the mirror of the famous-roster
  recall check: a roster of clearly-fictional names that must come back
  `UNKNOWN`. Deterministic (no judge), identify-only (no 70B agent), so it is
  cheap. This is the guard that drove the 8B → 70B model change — it failed
  4/4 on 8B and passes on 70B. Expressed as a high-floor *rate* (≥ 75% null)
  so it catches systematic fabrication without flaking on an occasional 70B
  slip.

`test-eval` and `test-e2e` skip cleanly when `GROQ_API_KEY` is absent, so they
stay green in dev environments without credentials.

## Engineering notes

- **Latency.** Scales with the (capped-at-5) name count. Identify is one LLM
  call per name (summarize on a wiki hit, identify-from-memory on a miss).
  Each *identified* person additionally drives the Ex5 agent — a tool-calling
  loop of ~2 calls (decide-to-look-up, then answer). Fictional `randomuser.me`
  names end at `UNKNOWN` and skip the agent entirely, so the expensive path
  only runs for people who actually exist.
- **Cost.** Both stages run on 70B, so cost is dominated by the 5-person cap
  rather than the model tier. The identify call is small (~150-400 tokens,
  one-shot); the agent adds ~2 calls per identified person. The 8B model would
  be ~10× cheaper per token, but it fabricates biographies (see the precision
  guard), and for this domain a correct answer is worth the spend. Wikipedia
  content is capped (600 chars for the identify summary, 1500 for the agent's
  tool result) to keep prompts tight.
- **Reliability.** Failures are typed at the boundary and translated into a
  single user-facing message with a non-zero exit code; no traceback
  reaches the user. `UserFetchError` (randomuser.me) prints a generic
  retry message; `groq.APIStatusError` (rate limit, context length, auth,
  5xx) prints Groq's own actionable message extracted from the response
  body.
