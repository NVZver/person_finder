# Test Suites: `validate_output` + repair retry loop (Epic 4)

The "user" of `validate_output` is the Epic 5 render layer (a Python caller, not a developer at a terminal). Journeys frame the contract from that caller's perspective. Every AC in [requirements.md](requirements.md) appears in at least one journey's **Covers:** field.

---

## Journey: Caller submits valid JSON on first try

**Goal:** A caller passes the agent's raw output (already valid JSON-shaped) to `validate_output` and gets the parsed dict back with no LLM cost incurred (`repair_fn` not called).
**Covers:** AC1

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — first-shot valid | caller: `validate_output(valid_raw, repair_fn=fixer)` → `json.loads` succeeds → shape check succeeds → returns `dict`; `fixer` never invoked |
| 2 | Happy — empty data list | caller: `validate_output('{"data": []}')` → returns `{"data": []}` (empty list is legal per spec) |

**Expected outcome:** Returned value equals the parsed JSON object. `repair_fn` (if supplied) sees zero invocations.

---

## Journey: Caller submits broken JSON; first repair fixes it

**Goal:** The agent's first output was malformed; the caller's `repair_fn` (Epic 5's closure-over-agent re-prompt) produces a valid retry on the first repair attempt. `validate_output` returns the dict; exactly one Groq round-trip happened inside `repair_fn`.
**Covers:** AC2, AC5 (partial — error message threads into `repair_fn`)

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — JSON parse error, repaired | initial `raw` is not JSON → `_ValidationFailure("JSON parse error: ...")` → `repair_fn(broken, msg)` returns valid JSON → returns parsed dict; `repair_fn` call count == 1; second arg to `repair_fn` contains the substring `"JSON parse error"` |
| 2 | Happy — shape error, repaired | initial `raw` parses but lacks `data` → `repair_fn` returns shaped JSON → success; same invocation pattern |

**Expected outcome:** `repair_fn` invoked exactly once with `(original_broken_raw, precise_error_msg)`; returned value equals the parsed repaired payload.

---

## Journey: Caller submits broken JSON; all 3 repairs also fail

**Goal:** The agent is stuck in a degenerate loop (or the upstream LLM is consistently malformed). `validate_output` exhausts the 3-repair budget and raises the spec-mandated `Error("Could not respond")`. The caller (Epic 5) catches this and surfaces it to the user.
**Covers:** AC3, AC5 (the chained `__cause__` carries the last precise error)

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Error — exhaust budget | `repair_fn` always returns malformed → `_ValidationFailure` raised 4 times (1 initial + 3 repairs) → after 3rd repair, `Error("Could not respond")` raised; `repair_fn` call count == 3 exactly |
| 2 | Error — `repair_fn` returns non-str | `repair_fn` returns `None` → `_ValidationFailure("repair output is not a str — got NoneType")` → counts against budget → same exhaustion path; `repair_fn` call count == 3 |

**Expected outcome:** `pytest.raises(Error)` catches `Error("Could not respond")`; `.__cause__` is the last `_ValidationFailure` with a precise message; `repair_fn` invocation count == 3 (the retry cap).

---

## Journey: Caller omits `repair_fn`; broken JSON fails fast

**Goal:** A caller that doesn't supply `repair_fn` (e.g. a unit test, or a future call site that doesn't want repair semantics) gets immediate failure when the raw input is malformed. No retries, no silent fallback.
**Covers:** AC4

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Error — immediate fail | `validate_output("not json")` → `_ValidationFailure` raised → no `repair_fn` to call → `Error("Could not respond")` raised immediately |
| 2 | Error — immediate fail on shape | `validate_output('{"data": "wrong"}')` → same path, shape variant |

**Expected outcome:** `Error("Could not respond")` raised on the very first failed validation; zero repair calls; chained `__cause__` carries the precise diagnostic.

---

## Journey: Each documented failure mode emits a precise diagnostic

**Goal:** For every documented violation kind, the `__cause__` of the raised `Error` carries a substring that names the violation + location. This makes debugging in Epic 5 possible without re-running with a debugger, and gives `repair_fn` the wording it needs to compose a targeted re-prompt.
**Covers:** AC5

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Malformed JSON | `validate_output("not json")` → `__cause__` contains `"JSON parse error"` |
| 2 | Top-level not dict (null) | `validate_output("null")` → `__cause__` contains `"top-level"` |
| 3 | Top-level not dict (list) | `validate_output("[]")` → `__cause__` contains `"top-level"` |
| 4 | Missing `data` key | `validate_output('{"other": 1}')` → `__cause__` contains `'"data"'` |
| 5 | `data` not a list | `validate_output('{"data": "nope"}')` → `__cause__` contains `"data"` |
| 6 | Missing `person` key | `validate_output('{"data": [{"info": "x"}]}')` → `__cause__` contains `"person"` |
| 7 | `info` not a str | `validate_output('{"data": [{"person": "Ada", "info": 7}]}')` → `__cause__` contains `"info"` |
| 8 | `person` not a str | `validate_output('{"data": [{"person": 42, "info": "x"}]}')` → `__cause__` contains `"person"` |
| 9 | `data[i]` not a dict | `validate_output('{"data": ["not a dict"]}')` → `__cause__` contains `"data[0]"` |

**Expected outcome:** Each path's chained `__cause__` is a `_ValidationFailure` whose message contains the documented substring. Verified via a single parametrized test (9 cases).

---

## Journey: Module import is side-effect-free

**Goal:** `import person_finder.validation` in a fresh interpreter does not read env vars, touch disk, raise, or instantiate `Settings()`. The module is safe to import from any context.
**Covers:** NF2

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — fresh subprocess | spawn `uv run python -c "import person_finder.validation"` in `tmp_path` with minimal env → exit 0; no traceback in stderr |

**Expected outcome:** Subprocess exits 0; stderr contains no traceback.

---

## Journey: Other tiers stay green

**Goal:** Adding `src/person_finder/validation.py` + `tests/unit/test_validation.py` does not regress the existing test pyramid.
**Covers:** AC6, NF5

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — unit tier grows | `make test-unit` before: 11 passed (5 agent + 6 config). After: 11 + N passed (N = new validation tests). |
| 2 | Happy — eval / e2e unaffected | `make test-eval` and `make test-e2e` collect the same set as before (both empty on `main`); exit 0 via swallow. |

**Expected outcome:** All three tiers exit 0; unit count grows by exactly the new validation tests; no agent / config tests touched.

---

## Journey: Spec graph wired

**Goal:** The `validation` module exists in the LSA spec graph: per-module spec at `specs/modules/validation/spec.md`, row in `main.spec.md` §Module Index, entry in `.lsa.yaml` under `modules:`.
**Covers:** AC7, F7

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — module spec exists | `ls specs/modules/validation/spec.md` succeeds; content follows the LSA module-spec template (Purpose / Scope / F / NF / AC / OQ). |
| 2 | Happy — main.spec.md updated | `grep '| validation ' specs/main.spec.md` matches; the linked file resolves. |
| 3 | Happy — .lsa.yaml updated | `validation:` block present under `modules:` with `spec` + `artifact_paths`; YAML structure remains valid. |

**Expected outcome:** Future `lsa:next` / `lsa:verify` runs can resolve `validation` as a known module.
