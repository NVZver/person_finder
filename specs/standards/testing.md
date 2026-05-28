# Testing Standards

Extracted from [ARCHITECTURE.md](../../ARCHITECTURE.md) §Tests / §Scripts.

## Test pyramid

### Unit — `tests/unit/`

- Framework: pytest.
- **All external calls mocked.**
- Coverage targets:
  - API fetch and response parsing
  - Filter and name-mapping logic
  - LangChain agent call
  - `validate_output`: valid input, broken JSON, schema mismatch
  - Retry loop: exhaustion and successful repair
  - `Error("Could not respond")` propagation and user-facing message

### LLM evaluation — `tests/eval/`

- Framework: DeepEval.
- Judge model: Gemini 2.0 Flash.
- Criteria:
  - Output is valid JSON with `person` and `info` fields.
  - `person` matches input list.
  - `info` is non-empty string or `"<Not found>"`.

### End-to-end — `tests/e2e/`

- Framework: pytest.
- **No mocks.**
- Coverage: full flow from API fetch to rendered output; validates output format.

## Scripts

```bash
make test-unit
make test-eval
make test-e2e
make test-all
```
