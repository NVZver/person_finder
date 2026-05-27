# Architecture

## Stack

| Component | Choice |
|---|---|
| Language | Python |
| Agent framework | LangChain |
| LLM | Groq - Llama 3.3 70B |
| Judge model | Gemini 2.0 Flash (Google AI Studio) |
| Testing | pytest, DeepEval |

---

## Layers

### 1. Python layer

- Fetches 20 users from `randomuser.me/api`
- Filters out people born after 2000
- Maps remaining response to `["First Last"]` name list
- Passes name list to agent layer
- Receives validated JSON and renders output
- On `Error("Could not respond")`: displays error message to user with instruction to retry later

### 2. LangChain agent layer

Runs a ReAct loop with Chain-of-Thought reasoning.

**System prompt defines:**
- Goal: find publicly available information for every person in the list
- Output schema: `{ "data": [{ "person": str, "info": str }] }`
- Fallback: `<Not found>` when no information is available

**Tool:**

```
findPerson(name: str) -> str
```

**`validate_output` — runs after the ReAct loop, not inside it:**
- Checks valid JSON
- Checks `data` key present
- Checks each item has `person` (str) and `info` (str)
- On failure: sends error + broken JSON back to LLM for repair
- Max retries: 3
- On retry limit: raises `Error("Could not respond")`
- Python layer only receives clean output

### 3. Groq - Llama 3.3 70B

Receives prompts, tool calls, and repair requests. Returns completions.

---

## Data flow

```
randomuser.me API
      |
Fetch 20 users
      |
Filter born after 2000
      |
Map to ["First Last"] name list
      |
LangChain ReAct loop
  findPerson(name) per person
  <Not found> on missing info
      |
validate_output()
  pass -> Python render -> user output
  fail -> retry with error + broken JSON (max 3)
       -> Error("Could not respond") on limit
              |
       Python catches -> user message + retry instruction
```

---

## Tests

### Unit (`tests/unit/`) — pytest, all external calls mocked

- API fetch and response parsing
- Filter and name mapping logic
- LangChain agent call
- `validate_output`: valid input, broken JSON, schema mismatch
- Retry loop: exhaustion and successful repair
- `Error("Could not respond")` propagation and user message

### LLM evaluation (`tests/eval/`) — DeepEval, Gemini 2.0 Flash as judge

Criteria:
- Output is valid JSON with `person` and `info` fields
- `person` matches input list
- `info` is non-empty string or `<Not found>`

### End-to-end (`tests/e2e/`) — pytest, no mocks

- Full flow from API fetch to rendered output
- Validates output format

---

## Scripts

```bash
make test-unit
make test-eval
make test-e2e
make test-all
```

---

## Environment variables

```
GROQ_API_KEY=       # https://console.groq.com
GOOGLE_API_KEY=     # https://aistudio.google.com
```
