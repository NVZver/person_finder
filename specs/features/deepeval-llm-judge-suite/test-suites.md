# Test Suites: DeepEval LLM-Judge Eval Suite (Epic 6)

Every AC in [requirements.md](requirements.md) appears in at least one journey's **Covers:** field. The "user" for these journeys is a developer running `make test-eval` (or the underlying `uv run pytest tests/eval/`).

---

## Journey: Run the eval suite with both keys + agent present

**Goal:** A developer with `GROQ_API_KEY` + `GOOGLE_API_KEY` in their host env, on a branch that already contains the LangChain agent module, runs `make test-eval` and gets a green run that proves the agent's output satisfies the three criteria.
**Covers:** AC1

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — clean run | `GROQ_API_KEY` + `GOOGLE_API_KEY` set → `person_finder.agent` importable → `make test-eval` → pytest collects ≥3 cases (one per criterion) → all pass → exit 0 |
| 2 | Happy — repeat run | Same prerequisites → re-run `make test-eval` → same green outcome → no flake (deterministic metrics; agent output may vary but criteria 1–3 hold across runs) |

**Expected outcome:** stdout shows `passed` for each of the three DeepEval test cases (one per criterion); the Gemini 2.0 Flash judge is configured but does not need to be invoked (criteria 1–3 are deterministic per F2/F3). `make test-eval` exits 0.

---

## Journey: Run the eval suite without `GOOGLE_API_KEY`

**Goal:** A developer (or CI without the Google AI Studio key provisioned) runs `make test-eval` and gets a clean skip — not a failure — because the judge cannot be configured.
**Covers:** AC2, NF6

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — clean skip | `GOOGLE_API_KEY` unset → `make test-eval` → all eval tests `skipped` with skip-reason naming `GOOGLE_API_KEY` → exit 0 |
| 2 | Edge — blank `GOOGLE_API_KEY` | `GOOGLE_API_KEY=""` (set but empty) → behave identically to unset → all skipped → exit 0 |

**Expected outcome:** stdout shows `skipped (GOOGLE_API_KEY unset)` (or equivalent) per eval test; exit 0. The unit + e2e tiers are unaffected (AC5 satisfied; see Journey "Other tiers stay green").

---

## Journey: Run the eval suite before the LangChain agent is merged

**Goal:** A developer on the `feature/deepeval-llm-judge-suite` branch — built independently of Epics 3–4 — runs `make test-eval` and gets a clean skip with a reason naming the missing agent module, so the branch can land safely.
**Covers:** AC3, NF6

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — clean skip on missing agent | `GOOGLE_API_KEY` set → `person_finder.agent` not importable → `make test-eval` → all eval tests `skipped` with skip-reason naming the agent module → exit 0 |
| 2 | Happy — clean skip when neither prerequisite is present | `GOOGLE_API_KEY` unset AND agent not importable → skip reason names the FIRST missing prerequisite encountered (judge key, then agent) — deterministic, single-line reason → exit 0 |

**Expected outcome:** stdout shows `skipped (person_finder.agent not importable yet — Epic 3 pending)` (or equivalent) per eval test; exit 0.

---

## Journey: Agent output violates a criterion

**Goal:** A developer modifies the agent (or a regression slips into the parallel branch) so that the agent emits a payload violating one of the three criteria. `make test-eval` shall fail loudly and the failure reason shall name the violated criterion.
**Covers:** AC4

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Error — malformed JSON | Agent returns a non-JSON string (or a JSON missing the `data` key) → `ValidJsonStructure` metric reports `success=False` with reason naming "JSON shape / `data` key / `person`/`info` types" → pytest case fails → `make test-eval` exits non-zero |
| 2 | Error — person not in input | Agent returns `data[].person` containing a name not present in the input list → `PersonNamesMatchInput` metric reports `success=False` with reason naming the offending name → pytest case fails → exit non-zero |
| 3 | Error — empty info | Agent returns `data[].info = ""` (empty string, not `"<Not found>"`) → `InfoNonEmptyOrSentinel` metric reports `success=False` with reason naming the offending entry → pytest case fails → exit non-zero |

**Expected outcome:** Each error path produces a single deterministic failure; the failure reason is precise enough that a developer can fix the agent without re-reading the eval source. Verified via stub-agent fixtures that emit controlled bad payloads — no real LLM call needed for AC4 (AC4 is a property of the metrics, not of the live agent).

---

## Journey: Other tiers stay green

**Goal:** Adding `tests/eval/` and its dependencies (DeepEval, Google SDK) does not regress `make test-unit` or `make test-e2e`.
**Covers:** AC5, NF5

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — unit tier unchanged | Run `make test-unit` before and after this epic merges → same set of tests collected → same pass count → no new imports leak into the unit tier |
| 2 | Happy — e2e tier unchanged | Run `make test-e2e` before and after → empty-collection exit 5 is still swallowed → exit 0 |
| 3 | Happy — `make test-all` green | `make test-all` runs unit → eval → e2e in order; with keys unset (the common dev case) all three exit 0 |

**Expected outcome:** unit + e2e behavior is byte-identical to pre-epic; only the eval tier is new.

---

## Journey: Spec wiring + roadmap hygiene

**Goal:** The `eval` module's existence is reflected in the project's spec graph: a module spec exists, `main.spec.md` lists it, and `.lsa.yaml` declares its artifact paths so future LSA skills can resolve it.
**Covers:** AC6

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy — spec graph wired | `specs/modules/eval/spec.md` created → `specs/main.spec.md` §Module Index gains an `eval` row linking to it → `.lsa.yaml` `modules:` gains an `eval:` entry → `roadmap.md` row 6 status flipped to `Done` at ship time |
| 2 | Happy — link integrity | Markdown links from `main.spec.md`, `roadmap.md`, and the module spec all resolve to live files (verified by a manual `ls` of the linked paths during the cross-reference sweep) |

**Expected outcome:** The next LSA run (e.g. `/lsa:next`) can resolve `eval` as a known module without falling back to the "new module" path.
