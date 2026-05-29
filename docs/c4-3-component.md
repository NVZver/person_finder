# C4 L3 — Component

Modules inside the CLI Application and how a run flows through them.

```mermaid
flowchart LR
    operator["<b>Operator</b>"]
    subgraph cli [CLI Application]
        direction LR
        main["<b>Entrypoint</b><br/><i>main.py</i><br/>orchestrate · errors · JSON"]
        loader["<b>Person Loader</b><br/><i>person_loader.py</i><br/>fetch · filter · cap"]
        agent["<b>Person Lookup Agent</b><br/><i>person_lookup_agent.py</i><br/>tool-calling · verify→repair→normalize"]
        tools["<b>Agent Tools</b><br/><i>tools.py</i><br/>lookup_person · lookup_best_work"]
        wiki["<b>Wikipedia Access</b><br/><i>wikipedia.py</i><br/>raw fetch · failure → 'no article'"]
        config["<b>Config + LLM Factory</b><br/><i>config.py</i>"]
        text["<b>Text Utils</b><br/><i>text.py</i>"]
    end
    randomuser["<b>randomuser.me</b>"]
    groq["<b>Groq LLM API</b>"]
    wikiapi["<b>Wikipedia API</b>"]

    operator --> main
    main -->|"get names"| loader
    main -->|"lookup_people(names)"| agent
    loader -->|"HTTPS / JSON"| randomuser
    agent -->|"binds / invokes"| tools
    agent -->|"chat (ChatGroq)"| groq
    agent -.->|"build_llm()"| config
    agent -.->|"is_unknown()"| text
    tools -->|"fetch_wiki_summary()"| wiki
    wiki -->|"HTTPS"| wikiapi

    classDef person   fill:#08427b,stroke:#052e56,stroke-width:1px,color:#ffffff;
    classDef internal fill:#1168bd,stroke:#0b4884,stroke-width:1px,color:#ffffff;
    classDef helper   fill:#5a4a8a,stroke:#3f3463,stroke-width:1px,color:#ffffff;
    classDef external fill:#6b6b6b,stroke:#4d4d4d,stroke-width:1px,color:#ffffff;
    class operator person;
    class main,loader,agent,tools,wiki internal;
    class config,text helper;
    class randomuser,groq,wikiapi external;
    style cli fill:none,stroke:#8a8a8a,stroke-width:1px,stroke-dasharray:5 5,color:#9aa0a6;
```

Solid edges = data flow · dotted = "uses" (helpers).

| Component | File | Responsibility |
|---|---|---|
| Entrypoint | `main.py` | wire pipeline, map errors, print |
| Person Loader | `person_loader.py` | fetch → filter (DOB ≤ 2000) → cap (≤5) |
| Person Lookup Agent | `person_lookup_agent.py` | own decision tree, enforce contract |
| Agent Tools | `tools.py` | expose Wikipedia as LLM tools |
| Wikipedia Access | `wikipedia.py` | wrap `wikipedia` lib |
| Config + LLM Factory | `config.py` | constants + one `ChatGroq` |
| Text Utils | `text.py` | `UNKNOWN` sentinel match |

## Defense in depth (every layer has a fallback)
| Failure | Caught in | Result |
|---|---|---|
| wiki miss / network | `wikipedia.py` | `None` → tool returns "no article" |
| tool finds nothing | agent (prompt) | fall back to model knowledge (`source:"llm"`) |
| can't identify | agent (prompt) | `UNKNOWN` → all fields null |
| contract violation | agent (`_verify`) | 1 repair retry → normalize to safe shape |
| randomuser/Groq down | `main.py` | clean stderr message, non-zero exit |

Smallest failure unit = one name / one field; nothing aborts the batch.

## Test pyramid (production-readiness proof)

```mermaid
graph TD
    E["<b>E2E</b> — tests/e2e<br/>real randomuser.me + Groq, full pipeline<br/><i>few · slow · highest confidence</i>"]
    EV["<b>Eval</b> — tests/eval<br/>live LLM scored by DeepEval metrics:<br/>valid JSON · recall · correctness · no hallucination"]
    U["<b>Unit</b> — tests/unit<br/>fully mocked: loader, agent contract, tools, config<br/><i>many · fast · no network</i>"]
    E --> EV --> U

    classDef e2e  fill:#c0392b,stroke:#7d2620,stroke-width:1px,color:#ffffff;
    classDef eval fill:#d68910,stroke:#9c6309,stroke-width:1px,color:#ffffff;
    classDef unit fill:#1e8449,stroke:#145a32,stroke-width:1px,color:#ffffff;
    class E e2e;
    class EV eval;
    class U unit;
```

- **Unit** — deterministic, mocked; proves plumbing + contract guard.
- **Eval** — LLM output can't use `==`; scored on validity / recall / correctness (LLM-judge) / precision (no hallucinated fictional names).
- **E2E** — full real pipeline; skips without `GROQ_API_KEY`.

⬅️ [L2 Container](./c4-2-container.md) · ➡️ [L4 Code](./c4-4-code.md)
