# C4 L2 — Container

Runnable units inside the system. ("Container" = process/datastore, not Docker.)

```mermaid
flowchart LR
    operator["<b>Operator</b><br/><i>Runs the CLI</i>"]
    subgraph pf [person_finder]
        cli["<b>CLI Application</b><br/><i>Python 3.12 process</i><br/>fetch names → agent per name → JSON"]
    end
    randomuser["<b>randomuser.me</b>"]
    groq["<b>Groq LLM API</b>"]
    wiki["<b>Wikipedia API</b>"]

    operator -->|Runs| cli
    cli -->|"GET people"| randomuser
    cli -->|"Tool-calling chat"| groq
    cli -->|"Fetch summaries"| wiki

    classDef person   fill:#08427b,stroke:#052e56,stroke-width:1px,color:#ffffff;
    classDef internal fill:#1168bd,stroke:#0b4884,stroke-width:1px,color:#ffffff;
    classDef external fill:#6b6b6b,stroke:#4d4d4d,stroke-width:1px,color:#ffffff;
    class operator person;
    class cli internal;
    class randomuser,groq,wiki external;
    style pf fill:none,stroke:#8a8a8a,stroke-width:1px,stroke-dasharray:5 5,color:#9aa0a6;
```

One synchronous process; sequential loop over ≤5 names.

**Notes**
- stdout = JSON, stderr = logs/errors (pipeable contract).
- Per-name work is independent and stateless (seam: `lookup_person_info`).

⬅️ [L1 Context](./c4-1-context.md) · ➡️ [L3 Component](./c4-3-component.md)
