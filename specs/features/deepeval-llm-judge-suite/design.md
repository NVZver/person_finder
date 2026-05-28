# Design: DeepEval LLM-Judge Eval Suite (Epic 6)

## Modules Affected
| Module | Change Type |
|--------|-------------|
| `eval` (new) | new — owns `tests/eval/**` and `specs/modules/eval/spec.md` |
| `scaffolding` | modify — `pyproject.toml` + `uv.lock` gain DeepEval + Google SDK deps; scaffolding spec already acknowledges cross-module `pyproject.toml` contributions via OQ3 |
| `agent` (Epic 3, parallel) | read-only — eval suite consumes its public surface via lazy import; never modifies it |
| `validation` (Epic 4, parallel) | read-only — eval suite asserts on the post-validation output; never modifies the retry loop |
| `specs/main.spec.md` | modify — Module Index gains `eval` row |
| `specs/roadmap.md` | modify (ship time) — Epic 6 status flipped to `Done` during cross-reference sweep |
| `.lsa.yaml` | modify — `modules:` gains `eval:` entry with `spec` + `artifact_paths` |

## Technical Approach

### Layer placement
The eval tier is **test infrastructure**, not application code. No file under `src/person_finder/` is touched. All judge wiring and metric classes live under `tests/eval/`:

```
tests/eval/
├── __init__.py              # marker only, empty
├── conftest.py              # fixtures: judge config, isolation override, agent_under_test
├── metrics.py               # three DeepEval BaseMetric subclasses (deterministic)
├── test_valid_json.py       # exercises ValidJsonStructure metric
├── test_person_matches.py   # exercises PersonNamesMatchInput metric
├── test_info_present.py     # exercises InfoNonEmptyOrSentinel metric
└── stub_agents.py           # canned bad-payload generators for AC4 (no LLM call)
```

Rationale: keeping metric classes in a separate `metrics.py` lets each `test_*.py` file pull only what it needs, and lets the future LLM-judged "info relevance" metric land in the same module without touching the deterministic three.

### Skip-or-run decision flow (F4, F5, NF2, NF6)

A single fixture `agent_under_test` in `tests/eval/conftest.py` resolves the run-vs-skip decision once per test (not per metric):

```
def agent_under_test(real_keys):
    if not real_keys.google_api_key:
        pytest.skip("GOOGLE_API_KEY unset — DeepEval judge cannot be configured")
    try:
        from person_finder.agent import run_agent  # name TBD by Epic 3
    except ImportError as exc:
        pytest.skip(f"person_finder.agent not importable yet — Epic 3 pending ({exc})")
    if not real_keys.groq_api_key:
        pytest.skip("GROQ_API_KEY unset — agent cannot reach Groq")
    return run_agent
```

The `real_keys` fixture (also in `tests/eval/conftest.py`) reads `os.environ` BEFORE the root `tests/conftest.py` autouse fixture strips the values — implementation note: pytest's autouse fixtures run in fixture-collection order; the eval conftest re-introduces the keys via `monkeypatch.setenv(...)` using values captured at session scope.

### Three deterministic metrics (F2)

Each metric is a `deepeval.metrics.BaseMetric` subclass with deterministic `measure(test_case)` logic:

| Metric class | Signal | success=True when |
|---|---|---|
| `ValidJsonStructure` | parses agent output as JSON → checks `data` key, list type, per-item `person:str` + `info:str` | All shape checks pass |
| `PersonNamesMatchInput` | parses output → set-membership check: every `data[].person` ∈ `set(input_names)` | All persons in input list |
| `InfoNonEmptyOrSentinel` | parses output → for each item: `info == "<Not found>"` OR `len(info.strip()) > 0` | All items pass |

Failure mode: `success=False` with `reason` naming the violated criterion + the offending entry (AC4).

### Judge model configuration (F3)

`tests/eval/conftest.py` configures DeepEval to use Gemini 2.0 Flash via the `google-generativeai` SDK as soon as `GOOGLE_API_KEY` is present:

```
# pseudocode — exact API call confirmed against context7 during implementation
deepeval.set_evaluation_model(GeminiFlash(api_key=os.environ["GOOGLE_API_KEY"]))
```

Even though the three deterministic metrics never call the judge, the configuration is exercised once at session-fixture scope and asserted via a unit-style check (`assert deepeval.evaluation_model.name == "gemini-2.0-flash"`) so AC6's "judge configured as Gemini 2.0 Flash" is observable without a live LLM call.

### AC4 verification strategy (bad-payload coverage)

AC4 ("agent output violates criterion → fail loudly with reason naming the violation") is a property of the **metrics**, not of the live agent. Verifying it with the live agent is impossible (we cannot force the real LLM to emit a malformed payload on demand) AND wasteful (LLM call per failure mode). Instead:

- `tests/eval/stub_agents.py` provides three canned bad-payload generators: `malformed_json()`, `unknown_person()`, `empty_info()`.
- One pytest test per failure mode feeds the stub payload through the corresponding metric and asserts `metric.success is False` and `expected_substring in metric.reason`.

This keeps AC4 fast, deterministic, and isolated from the live agent — and the same stubs document the failure-reason format for future maintainers.

### Test data (F5)

A module-level constant in `tests/eval/conftest.py`:

```
PUBLIC_FIGURES: list[str] = ["Albert Einstein", "Marie Curie"]
```

Two names keep cost ≤ $0.05/run (NF1). The roster is not parameterized over `randomuser.me` (whose names are unknown to the LLM and would defeat the eval).

## Data Model Changes

None. This feature consumes the existing agent output contract from `main.spec.md:20` read-only.

## API / Interface Changes

None. (Contract trigger = NO per User Verification 1.)

## Cross-Module Contracts

None new. The feature consumes the existing cross-module contract:

```
Name list  (Python → Agent):  list[str] of "First Last"
Enrichment result (Agent → Python):  { "data": [{ "person": str, "info": str }] }
```

Per [main.spec.md §Cross-Module Contracts](../../main.spec.md) lines 17-23. The eval suite has no write access to this contract.

## Dependency Additions (pyproject.toml)

```toml
[dependency-groups]
dev = [
    "pytest>=8,<9",
    "deepeval>=2,<3",            # version TBD on first install; pin minor at impl time
    "google-generativeai>=0.8",  # Gemini 2.0 Flash judge SDK
]
```

Rationale:
- Both deps land under `dev` (not top-level `dependencies`) — they are not application runtime deps. Splitting into a separate `[dependency-groups] eval` group is deferred (requirements OQ3) until eval-only deps balloon.
- `deepeval` version range pinned at implementation time against the actually-installed version (OQ2 may force a wider/narrower range based on what DeepEval pulls in at import).
- `google-generativeai` chosen over `langchain-google-genai` because the eval suite must NOT depend on LangChain — LangChain is the agent's framework, not the eval suite's. If the parallel branch happens to also pull in `google-generativeai`, the lockfile resolves to a single version.

## Open Questions

| # | Question | Decision point |
|---|---|---|
| OQ1 | Agent public-surface shape — `agent.run(names)`, `agent.find_people(names)`, or async equivalent? Eval suite lazy-imports a single named function; the name is adjusted once Epic 3's PR opens. | Resolved when Epic 3 lands; adjust the `from person_finder.agent import ...` line and re-run. |
| OQ2 | Does `deepeval` import a heavyweight LLM-judge stack (e.g. `openai`) at module load that breaks NF4? Determined on first `uv sync` after this epic ships. If yes, wrap DeepEval imports in `pytest.importorskip("deepeval")` at the conftest level so a missing/broken install also degrades to skip. | Resolved at first install. |
| OQ3 | If `make test-eval` ever needs to call the judge (when a future "info relevance" metric is added), what cost ceiling do we enforce? | Deferred to the follow-up epic that introduces the LLM-judged metric. |
| OQ4 | Should the `agent_under_test` fixture skip on `ImportError` ONLY, or also on `ModuleNotFoundError` of a missing transitive dep (e.g. LangChain not installed in the eval env)? Current design uses `try/except ImportError` which catches both. | Resolved by design above; revisit if a transitive-import quirk surfaces. |
| OQ5 | The `tests/conftest.py` autouse fixture strips both keys via `monkeypatch.delenv`. The eval conftest must re-set them *before* the autouse fixture observes that they're missing. This requires reading `os.environ` at module-import time (session-scope cache), then re-emitting via `monkeypatch.setenv` inside the eval-scoped fixture. Confirm the ordering works as designed; if pytest's fixture resolution interferes, fall back to changing the root autouse fixture to skip eval tests by `pytestmark`. | Resolved at implementation time via a quick smoke test. |
