# C4 L2 — Container

Runnable units inside the system. ("Container" = process/datastore, not Docker.)

## Current — single-process CLI

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

One synchronous process; sequential loop over ≤5 names. Correct size for a 5-item batch.

## Evolved — as a service (scaling reference)

```mermaid
flowchart LR
    client["<b>Client</b><br/><i>Submits a batch</i>"]
    subgraph pf [person_finder service]
        direction LR
        api["<b>API / Ingest</b><br/><i>FastAPI</i><br/>auth · rate-limit · returns job id"]
        queue(["<b>Job Queue</b><br/><i>SQS / Redis</i>"])
        worker["<b>Lookup Worker</b><br/><i>Python pool</i><br/>agent per name · scales out"]
        cache[("<b>Result + Source Cache</b><br/><i>Redis / Postgres</i>")]
    end
    groq["<b>Groq LLM API</b>"]
    wiki["<b>Wikipedia API</b>"]

    client -->|"POST /batch"| api
    api -->|enqueue| queue
    queue -->|"pull jobs"| worker
    worker -->|"read-through / write"| cache
    worker -->|"tool-calling chat"| groq
    worker -->|"fetch summaries"| wiki

    classDef person   fill:#08427b,stroke:#052e56,stroke-width:1px,color:#ffffff;
    classDef internal fill:#1168bd,stroke:#0b4884,stroke-width:1px,color:#ffffff;
    classDef store    fill:#3a7d44,stroke:#27562f,stroke-width:1px,color:#ffffff;
    classDef external fill:#6b6b6b,stroke:#4d4d4d,stroke-width:1px,color:#ffffff;
    class client person;
    class api,worker internal;
    class queue,cache store;
    class groq,wiki external;
    style pf fill:none,stroke:#8a8a8a,stroke-width:1px,stroke-dasharray:5 5,color:#9aa0a6;
```

| Concern | CLI today | Service |
|---|---|---|
| Concurrency | sequential loop | worker pool off a queue |
| Spikes | operator-paced | queue absorbs / back-pressure |
| Cost + latency | re-asks LLM each run | cache name→result + wiki summaries |
| Rate limits | surface + exit | token-bucket at edge + retry/backoff |
| Failure unit | per-row fallback | + dead-letter queue |

**Notes**
- Scaling axis = the per-name unit (independent, stateless). Seam already exists: `lookup_person_info`.
- First addition under load = cache (LLM + wiki calls dominate cost/latency; inputs repeat).
- stdout = JSON, stderr = logs/errors (pipeable contract).

⬅️ [L1 Context](./c4-1-context.md) · ➡️ [L3 Component](./c4-3-component.md)
