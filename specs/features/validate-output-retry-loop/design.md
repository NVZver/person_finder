# Design: `validate_output` + repair retry loop (Epic 4)

## Modules Affected

| Module | Change Type |
|--------|-------------|
| `validation` (new) | new — owns `src/person_finder/validation.py`, `tests/unit/test_validation.py`, `specs/modules/validation/spec.md` |
| `agent` (Epic 3, already on main at `659fca7`) | read-only — `validate_output` does NOT import the agent; Epic 5 supplies `repair_fn` as a closure over `agent.enrich_names` |
| `scaffolding` | not touched — `pyproject.toml`, `uv.lock`, `tests/conftest.py` all stay as-is (stdlib `json` only) |
| `specs/main.spec.md` | modify — add `validation` row (and fix-it-forward `agent` row missed by Epic 3) to §Module Index, trim those names from the "Future modules" sentence |
| `.lsa.yaml` | modify — add `validation:` entry under `modules:` with `spec` + `artifact_paths` |
| `specs/roadmap.md` | not touched here — Epic 4 status flip happens at ship-time sweep |

## Technical Approach

### Public surface

```python
# src/person_finder/validation.py

MAX_REPAIRS: Final[int] = 3

class Error(Exception):
    """Cross-module failure signal per main.spec.md:24."""

def validate_output(
    raw: str,
    repair_fn: Callable[[str, str], str] | None = None,
) -> dict[str, Any]:
    ...
```

Two symbols are public (`Error`, `validate_output`); everything else is `_`-prefixed.

### Retry loop shape

```python
current = raw
last_failure: _ValidationFailure | None = None

for attempt in range(MAX_REPAIRS + 1):  # 1 initial + 3 repairs
    try:
        return _parse_and_check(current)
    except _ValidationFailure as exc:
        last_failure = exc
        if repair_fn is None or attempt == MAX_REPAIRS:
            break
        current = repair_fn(current, str(exc))

raise Error("Could not respond") from last_failure
```

- `range(MAX_REPAIRS + 1)` = 4 iterations: 1 initial attempt + up to 3 repairs.
- `attempt == MAX_REPAIRS` is the 4th iteration — at that point we've already done 3 repair calls; no further `repair_fn` call. Break and raise.
- `from last_failure` chains the precise diagnostic to the public `Error` via `__cause__`.

### Error hierarchy

- **Public `Error(Exception)`** — module-local symbol named per spec letter (`main.spec.md:24`). Single argument `"Could not respond"`. No subclass info; the contract is just the string.
- **Private `_ValidationFailure(Exception)`** — internal. Carries the precise human-readable diagnostic intended for `repair_fn`'s `error_msg` argument. Never raised outside this module; only attached to the public `Error` via `__cause__`.

### Parse + check pipeline

```
_parse_and_check(raw: Any) -> dict[str, Any]
  ├─ isinstance(raw, str)?       → no  → _ValidationFailure("repair output is not a str — got <type>")
  ├─ json.loads(raw)             → fail → _ValidationFailure("JSON parse error: <stdlib msg>")
  └─ _check_shape(parsed)        → see below

_check_shape(payload: Any) -> dict[str, Any]
  ├─ isinstance(payload, dict)?  → no  → _ValidationFailure("top-level is not a dict — got <type>")
  ├─ "data" in payload?          → no  → _ValidationFailure('missing "data" key at top level')
  ├─ isinstance(data, list)?     → no  → _ValidationFailure("data is not a list — got <type>")
  └─ for each item:
       ├─ isinstance(item, dict)?     → no  → _ValidationFailure("data[i] is not a dict — got <type>")
       ├─ "person" in item?           → no  → _ValidationFailure('data[i] missing "person" key')
       ├─ isinstance(item["person"], str)? → no → _ValidationFailure("data[i].person is not a str — got <type>")
       ├─ "info" in item?             → no  → _ValidationFailure('data[i] missing "info" key')
       └─ isinstance(item["info"], str)?   → no → _ValidationFailure("data[i].info is not a str — got <type>")
```

`_parse_and_check` takes `Any` rather than `str` because `repair_fn` might mis-return a non-string; we want that to count as a normal validation failure (one budget unit), not a `TypeError` crash. The `isinstance(raw, str)` guard sits ahead of `json.loads`.

### `repair_fn` contract

```
repair_fn: Callable[[str, str], str]
```

- **Arg 1** — `broken_raw: str` — verbatim the LLM's last bad output.
- **Arg 2** — `error_msg: str` — human-readable description of WHAT failed, formatted by `_ValidationFailure`. Examples: `"JSON parse error: Expecting value"`, `'missing "data" key at top level'`, `"data[2].info is not a str — got int"`.
- **Return** — `str` (a freshly repaired attempt). Validation re-runs against this string. Any non-`str` return is caught defensively (see NF3) and counts as a normal failure.

Validation does NOT compose the repair prompt — that's Epic 5's job. Validation just exposes the broken-raw + precise-error pair.

### Why validation does NOT import the agent

Three reasons:

1. **Testability.** Unit tests can pass `repair_fn = lambda broken, err: ...` and exercise every branch without spinning up LangChain. Mirrors `tests/conftest.py`'s "all external calls mocked" stance for the unit tier.
2. **Reusability.** Future repair sources (e.g. a non-LLM heuristic, a cached repair table) plug in via the same `repair_fn` contract without touching `validation.py`.
3. **Module-boundary discipline.** The validation module's job is to validate. The agent module's job is to enrich. Wiring them is Epic 5 (`render`).

### `Error` name — spec letter vs Pythonicity

`main.spec.md:24` says the failure signal is `Error("Could not respond")`. Two reads:

- **Literal** — define a `class Error(Exception)` in `validation.py`.
- **Idiomatic** — interpret `Error` as "some exception, name TBD" and use e.g. `RuntimeError`.

This design chooses **literal**. Rationale: the cross-module contract is a typed handshake; renaming it to `RuntimeError` would force every consumer to remember the unconventional spec / type mismatch. The module docstring warns against `from person_finder.validation import *` and instructs callers to `from person_finder.validation import Error` explicitly. Python has no builtin `Error` so no actual builtin is shadowed.

## Data Model Changes

None. The function operates on a JSON-shaped `str` and returns a Python `dict`.

## API / Interface Changes

None to the cross-module contract from `main.spec.md:19-26` (§Cross-Module Contracts block). This feature implements that contract; it does not extend it.

(No `contract.yaml` — trigger NO at User Verification 1. There is no HTTP endpoint, no request/response schema, no DB schema, no new shared type. The agent's output shape was already declared in `main.spec.md:22`; validation enforces it.)

## Cross-Module Contracts

- **Consumed (read-only):** `main.spec.md:22` `{"data": [{"person": str, "info": str}]}` — the agent's output shape that validation enforces.
- **Owned:** `main.spec.md:24` `Error("Could not respond")` — the failure signal Epic 5 catches. This feature defines the concrete exception class at `person_finder.validation.Error`.

## Open Questions

| # | Question | Decision point |
|---|---|---|
| OQ1 | `agent` row in `main.spec.md` §Module Index — Epic 3 (merged at `659fca7`) created the agent module spec + `.lsa.yaml` entry but did not add the Module Index row. This feature adds it fix-it-forward. | Verify-time accept; alternative is to revert and let Epic 5 do it. |
| OQ2 | `raw: str` vs `raw: str | bytes`? `json.loads` accepts both, but the agent contract returns `str`. Widening is deferred until a real `bytes` source surfaces. | Deferred; no impact on current callers. |
| OQ3 | `MAX_REPAIRS` configurable via parameter? Currently `Final[int] = 3` per spec letter. Configurable would weaken the contract. | Deferred until a real use case appears. |
| OQ4 | Should `validate_output` accept a `pre_parse: bool` flag for callers who already have a `dict`? Currently no — the function's job is parse-then-check. A pre-parse caller can just call `_check_shape` directly (private — would have to be re-exported). | Deferred. |
