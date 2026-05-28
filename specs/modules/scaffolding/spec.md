# Scaffolding Module — Spec

## Purpose

Provide the Python project skeleton (build config, test layout, dev scripts) plus a minimal env-var loader so feature modules (fetch, agent, validation, render, eval — Epics 2–6) can write code, run `make test-unit` to a zero-test green, and read `GROQ_API_KEY` / `GOOGLE_API_KEY` at import time without re-inventing the loader per module.

Pitch source: [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Stack, §Scripts, §Env vars, §Tests.
Epic: [roadmap.md](../../roadmap.md) row 1 (`Project scaffolding & env loading`, MVP).

## Scope (artifact paths)

- `pyproject.toml`, `uv.lock`, `Makefile`, `.env.example`
- `src/person_finder/{__init__,config}.py`
- `tests/conftest.py`, `tests/unit/__init__.py`, `tests/unit/test_config.py`
- `tests/{eval,e2e}/` (directories only — contents owned by future modules)

## Functional requirements

- **F1 — Package layout.** Python package at `src/person_finder/`; `pyproject.toml` declares wheel package via src/ layout. Installable via `uv sync` or `pip install -e .`.
- **F2 — Test pyramid scaffolding.** Three test tiers as directories: `tests/unit/` (mocked), `tests/eval/` (DeepEval+Gemini), `tests/e2e/` (no mocks). Dedicated Makefile targets per tier (`make test-unit/eval/e2e`) plus `make test-all`. Empty tiers exit 0.
- **F3 — Env loader.** `person_finder.config.Settings` (a `BaseSettings`) loads `GROQ_API_KEY` + `GOOGLE_API_KEY` from process env first, then from `.env` in CWD. Both fields required and non-blank (`Field(min_length=1)`).
- **F4 — Settings access pattern.** Production code reads settings via `get_settings()` — an `lru_cache`-wrapped accessor that lazily instantiates `Settings()` on first call. The `Settings` class is NOT instantiated at module top.
- **F5 — Env template.** `.env.example` is committed with both key names + empty values + comments pointing to upstream consoles. `.env` itself is gitignored.

## Non-functional requirements / invariants

- **NF1 — Build tool: uv.** Managed by uv ≥ 0.11; no Poetry, no pip-tools, no raw `requirements.txt`. `uv.lock` committed.
- **NF2 — Python pin: 3.12.** `requires-python = ">=3.12,<3.13"`. Other Python versions unsupported.
- **NF3 — Fail loud on missing/blank env keys.** `Settings()` MUST raise `pydantic.ValidationError` if either key is missing OR blank. Silent fallbacks to empty strings are not acceptable.
- **NF4 — Test isolation against both env and disk.** Tests must be isolated from process env AND `.env` at repo root. Mechanism: autouse fixture in `tests/conftest.py` deletes both env vars AND `chdir`s into per-test `tmp_path`. Adding a new "missing key" test MUST verify isolation holds with a populated `.env` present.
- **NF5 — Side-effect-free imports.** `import person_finder.config` MUST NOT read env, read disk, or raise. Validation runs only on `Settings()` / `get_settings()` invocation.
- **NF6 — POSIX make.** Makefile relies on POSIX shell for the `|| [ $$? -eq 5 ]` trick that swallows pytest's "no tests collected" exit-5. Windows native shells unsupported (use WSL).

## Acceptance criteria

- **AC1** — `make test-unit` exits 0. Currently satisfied: 6 passing tests.
- **AC2** — `make test-all` exits 0. Currently satisfied: all three tiers green.
- **AC3** — `get_settings()` returns the same instance on repeated calls. Currently verified by `test_get_settings_is_cached`.
- **AC4** — `Settings()` raises `pydantic.ValidationError` on missing OR blank keys. Currently verified by 3 tests in `test_config.py`.

## Open questions / follow-ups

| # | Question | Source |
|---|---|---|
| OQ1 | Lint + type-check tooling (ruff, mypy) — not in constitution. | Developer agent self-review. |
| OQ2 | CI provisioning of `uv` — not yet automated; developers currently install via `astral.sh/uv` script. | Developer agent trade-off #5. |
| OQ3 | `.idea/` (JetBrains) gitignore — `.gitignore:189` commented out; auto-created during dev sessions. | Side-channel finding; not strictly module-scoped. |
| OQ4 | Lockfile strategy for prod vs. dev — currently one `uv.lock` covers both. Revisit if eval / e2e deps drift apart. | Developer agent default. |
