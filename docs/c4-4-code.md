# C4 L4 — Code

Zoom into one component: **Person Lookup Agent** (`person_lookup_agent.py`) — where the LLM meets a strict contract. Other components stay at L3.

## Contract — `PersonResult`

```python
class PersonResult(BaseModel):
    info: str | None = None                       # who they are, or None
    source: Literal["wiki", "llm"] | None = None  # where identity came from
    best_work: str | None = None                  # notable work, or None
```

| State | info | source | best_work |
|---|---|---|---|
| Unknown | null | null | null |
| Identified · grounded | set | `wiki` | set/null |
| Identified · from model | set | `llm` | set/null |

Invariants: `info`↔`source` paired; `best_work` only when identified.

```mermaid
flowchart LR
    start([PersonResult]) --> q{info = real person?}
    q -- no --> unk["<b>Unknown</b><br/>all null"]
    q -- yes --> q2{source in wiki/llm?}
    q2 -- yes --> ok["<b>Identified</b><br/>info+source paired"]
    q2 -- no --> bad["<b>Violation</b><br/>→ repair/coerce"]

    classDef neutral fill:#1168bd,stroke:#0b4884,stroke-width:1px,color:#ffffff;
    classDef good fill:#1e8449,stroke:#145a32,stroke-width:1px,color:#ffffff;
    classDef bad  fill:#c0392b,stroke:#7d2620,stroke-width:1px,color:#ffffff;
    classDef dec  fill:#5a4a8a,stroke:#3f3463,stroke-width:1px,color:#ffffff;
    class start,ok neutral;
    class unk good;
    class bad bad;
    class q,q2 dec;
```

## Call graph

```mermaid
flowchart LR
    lp["<b>lookup_people()</b><br/><i>loops names</i>"]
    lpi["<b>lookup_person_info()</b><br/><i>one name, safe</i>"]
    build["<b>build_person_lookup_agent()</b>"]
    invoke["_invoke()"]
    probs["_problems()"]
    verify["_verify()"]
    coerce["_coerce()"]
    create["create_agent()<br/><i>LangChain</i>"]
    llm["config.build_llm()"]

    lp --> lpi
    lp --> build
    build --> create
    build -.-> llm
    lpi --> invoke
    lpi --> probs
    probs --> verify
    lpi --> coerce

    classDef pub  fill:#1168bd,stroke:#0b4884,stroke-width:1px,color:#ffffff;
    classDef priv fill:#5a4a8a,stroke:#3f3463,stroke-width:1px,color:#ffffff;
    classDef ext  fill:#6b6b6b,stroke:#4d4d4d,stroke-width:1px,color:#ffffff;
    class lp,lpi,build pub;
    class invoke,probs,verify,coerce priv;
    class create,llm ext;
```

Agent built once in `lookup_people`, reused across names.

## verify → repair → coerce

```mermaid
flowchart TD
    a["_invoke — attempt 1"] --> r1{valid?}
    r1 -- yes --> done["coerce → row"]
    r1 -- no --> repair["_invoke with problems — attempt 2"]
    repair --> r2{result?}
    r2 -- None --> nullrow["PersonResult() — all null"]
    r2 -- yes --> coerce["coerce → safe shape"]
    coerce --> done2["row"]

    classDef step fill:#1168bd,stroke:#0b4884,stroke-width:1px,color:#ffffff;
    classDef dec  fill:#5a4a8a,stroke:#3f3463,stroke-width:1px,color:#ffffff;
    classDef good fill:#1e8449,stroke:#145a32,stroke-width:1px,color:#ffffff;
    classDef warn fill:#d68910,stroke:#9c6309,stroke-width:1px,color:#ffffff;
    class a,repair,coerce step;
    class r1,r2 dec;
    class done,done2 good;
    class nullrow warn;
```

```python
def lookup_person_info(name: str, *, agent: Any) -> PersonResult:
    result = _invoke(agent, name)                       # 1. attempt
    problems = _problems(result)                        # 2. VERIFY
    if problems:
        result = _invoke(agent, name, repair=problems)  # 3. REPAIR (1 retry, errors fed back)
    if result is None:
        return PersonResult()                           # 4a. safe null row
    return _coerce(result)                              # 4b. COERCE → valid shape
```

```python
def _verify(result: PersonResult) -> list[str]:
    problems: list[str] = []
    if not _identified(result):
        if result.source is not None:
            problems.append("source must be null when the person is not identified")
        if result.best_work:
            problems.append("best_work must be null when the person is not identified")
    elif result.source not in ("wiki", "llm"):
        problems.append("source must be 'wiki' or 'llm' when info is present")
    return problems
```

```python
def _coerce(result: PersonResult) -> PersonResult:
    if not _identified(result):
        return PersonResult(info=None, source=None, best_work=None)
    best = result.best_work if (result.best_work and not is_unknown(result.best_work)) else None
    source = result.source if result.source in ("wiki", "llm") else "llm"  # default low-trust, keep recall
    return PersonResult(info=result.info, source=source, best_work=best)
```

Pattern: validate boundary → bounded self-heal → deterministic degrade.

## Dynamic — one name

```mermaid
flowchart TD
    s["lookup_person_info(name)"] --> inv["agent.invoke"]
    inv --> llm1["LLM: call lookup_person?"]
    llm1 --> tool1["lookup_person → Wikipedia"]
    tool1 --> id{identified?}
    id -- no --> unk["UNKNOWN (null)"]
    id -- yes --> llm2["lookup_best_work → Wikipedia"]
    llm2 --> struct["PersonResult"]
    unk --> struct
    struct --> guard["verify→repair→coerce"]
    guard --> row["row in data[]"]

    classDef step fill:#1168bd,stroke:#0b4884,stroke-width:1px,color:#ffffff;
    classDef model fill:#08427b,stroke:#052e56,stroke-width:1px,color:#ffffff;
    classDef dec  fill:#5a4a8a,stroke:#3f3463,stroke-width:1px,color:#ffffff;
    classDef good fill:#1e8449,stroke:#145a32,stroke-width:1px,color:#ffffff;
    class s,inv,tool1,struct,guard step;
    class llm1,llm2 model;
    class id dec;
    class unk,row good;
```

Agent (not our code) decides whether/when to call tools, per `SYSTEM_PROMPT`.

## Edge cases

| Failure | Handled in | Defense |
|---|---|---|
| no structured output | `_problems(None)` | violation → repair, else null row |
| duplicate structured call | `config.build_llm` | `parallel_tool_calls=False` |
| `"UNKNOWN"` / empty / `"unknown."` | `text.is_unknown` | case/punct-tolerant match |
| garbage `source` when identified | `_coerce` | default to `llm`, keep identification |
| wiki down / no article | `wikipedia.py` → `tools.py` | returns string, never raises |

**Notes**
- `_verify` / `_coerce` / `_identified` / `is_unknown` are pure → no-mock unit tests; only `_invoke` is impure.
- Unit tests feed a stub agent returning broken results, assert the row comes out valid.
- `SYSTEM_PROMPT` is version-controlled code, not a magic string.

⬅️ [L3 Component](./c4-3-component.md)
