# Verify Warnings — langchain-agent

**Verified:** 2026-05-28
**Verdict:** PASS WITH WARNINGS (accepted by user; proceed to sync)
**Branch:** `feature/langchain-agent` (worktree `../person_finder-epic3`, off `main`)
**Verify mode:** `code` per `.lsa.yaml`

No `metrics.md` written — per `/lsa:verify` skill: "No metrics.md write on FAIL or PASS WITH WARNINGS."

## Warnings

### W1 — Feature spec files outside epic Scope union (orphan-diff + scope-union)

**Files flagged:** `specs/features/langchain-agent/{requirements,test-suites,design,tasks}.md`

**Why filtered, not failed:** These four files were authored by `/lsa:discover` and `/lsa:plan` on the same branch as implementation. They appear in `git diff main` even though they are the *trace target* of verify, not implementation output. Strict reading of the orphan-diff predicate calls this FAIL; pragmatic reading (the spec cannot trace to itself) accepts it.

**Underlying skill↔flow gap:** `/lsa:verify` implicitly assumes the feature spec lands on `main` BEFORE the implementation branch starts, so by verify time the spec dir is no longer in the diff. The `/lsa:next` flow we ran does NOT enforce that interim merge — it authors the spec on the same branch as the implementation. Either:
- `/lsa:verify` needs an explicit filter clause for the `specs/features/<name>/` dir, or
- `/lsa:next` (or `/lsa:discover`/`/lsa:plan`) needs an interim "commit spec, merge to main, branch again" step before handing off to `/lsa:implement`.

**Follow-up:** raise with LSA-skill maintainer; no implementation work needed for this feature.

### W2 — `test-suites.md` declares 3 journeys; no `tests/e2e/` files added

**Detail:** `test-suites.md` declares journeys *Enrich a name list*, *Fail loud when GROQ_API_KEY is missing*, *Import the module without side effects*. Zero files added under `tests/e2e/`.

**Why filtered, not failed:** `requirements.md` §Out of Scope (lines 42–47) explicitly defers e2e to Epic 5 (`render` module). The journeys ARE exercised at unit tier with a mocked LLM, which is the correct tier for Epic 3's surface (an internal Python module with no cross-process boundary). The verify checklist row "E2E tests cover all journeys" reads literally and doesn't account for explicit out-of-scope deferrals in the feature spec itself.

**Follow-up:** when Epic 5 lands, its tests should exercise these 3 journeys end-to-end. Worth re-reading this warning then to confirm coverage closes.

### W3 — Edge case + error-path asymmetry in unit tests

**Detail:**
- `enrich_names(None)` is unhandled — would `TypeError` on `'\n'.join`. No explicit guard.
- AC1 has no test for `agent.invoke` raising (e.g., HTTP error from Groq propagating through).

**Why filtered, not failed:** Type contract is `list[str]`; per Python convention the caller bears responsibility for type discipline. AC1 doesn't promise exception-propagation semantics — that's also Epic 4's territory (validate_output + repair-retry loop). Minor.

**Follow-up:** A 4-line test of `enrich_names` over a fake whose `.invoke` raises would close this in a follow-up commit if desired. Not a release blocker.
