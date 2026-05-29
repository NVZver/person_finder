# C4 L1 — System Context

Who uses `person_finder` and what it depends on.

```mermaid
flowchart TB
    operator["<b>Operator</b><br/><i>Runs the CLI to enrich a<br/>batch of people into JSON</i>"]
    pf["<b>person_finder</b><br/><i>Identifies each person and their<br/>best work → verified JSON</i>"]
    randomuser["<b>randomuser.me</b><br/><i>Random user records<br/>(name, DOB)</i>"]
    groq["<b>Groq LLM API</b><br/><i>llama-3.3-70b<br/>the reasoning engine</i>"]
    wiki["<b>Wikipedia API</b><br/><i>Grounding<br/>source of truth</i>"]

    operator -->|"Runs (CLI / stdout JSON)"| pf
    pf -->|"Fetch people (HTTPS)"| randomuser
    pf -->|"Reason and decide (tool-calling)"| groq
    pf -->|"Ground answers (HTTPS)"| wiki

    classDef person   fill:#08427b,stroke:#052e56,stroke-width:1px,color:#ffffff;
    classDef internal fill:#1168bd,stroke:#0b4884,stroke-width:1px,color:#ffffff;
    classDef external fill:#6b6b6b,stroke:#4d4d4d,stroke-width:1px,color:#ffffff;
    class operator person;
    class pf internal;
    class randomuser,groq,wiki external;
```

| Element | Type | Role |
|---|---|---|
| Operator | person | Triggers a run (CLI). No UI, no inbound API |
| person_finder | system | Batch enrichment: names → source-attributed facts |
| randomuser.me | external | Input — name + DOB |
| Groq LLM API | external | Reasoning / tool-calling decisions |
| Wikipedia API | external | Grounding source; answers tagged `wiki` vs `llm` |

**Notes**
- Batch system, no inbound traffic → no auth / LB / scaling at this level.
- Two non-deterministic/unreliable deps (LLM, public API) → reliability is engineered in-process, not assumed upstream.

➡️ [L2 Container](./c4-2-container.md)
