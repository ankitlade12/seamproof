# Architecture

SeamProof has two halves: the **system under test (SUT)** — a real UiPath Maestro
process — and **SeamProof** — the tester that reads the SUT's run traces and gates
the release. They are decoupled by a single artifact: the **run trace**.

```
                          ┌─────────────────────────────────────────────┐
                          │        SYSTEM UNDER TEST (Maestro)           │
   test inputs            │                                              │
   (varied + ───────────► │  [Recon Agent] → [Router] → [Human] → [Robot]│
   adversarial)           │   Agent Builder   Maestro   Action    Studio │
        │                 │   / LangChain               Center           │
        │                 └───────────────────┬──────────────────────────┘
        │                                      │  run trace (events + context)
        │                                      ▼
        │           ┌──────────────────────────────────────────────────┐
        │           │                     SEAMPROOF                      │
        │           │                                                    │
        └─────────► │  Trace  →  Evaluation doc per seam  →  Assertions  │
                    │  model      (handoff/context/events)     (kinds)   │
                    │                                  │                  │
                    │                                  ▼                  │
                    │              Gate (blocking / advisory)            │
                    │                                  │                  │
                    │         ┌────────────────────────┼───────────────┐ │
                    │         ▼          ▼              ▼               ▼ │
                    │       text      markdown        json          junit│
                    └──────────────────────────────────┼───────────────┘ │
                                                        ▼
                              go / no-go release gate (exit code → CI / Test Manager)
```

## The contract: a run trace

A trace is platform-neutral JSON. Anything that can emit this shape — a Maestro
audit export, a LangChain callback handler, or a hand-written fixture — can feed
SeamProof.

```jsonc
{
  "trace_id": "run-...",
  "process": "invoice-exception-handling",
  "context": {                      // static facts the run executed against
    "po": { "currency": "USD", "vendor_id": "V-1042" },
    "approved_vendor_master": ["V-1042", "..."],
    "auto_post_ceiling": 10000,
    "human_review_floor": 9000,
    "min_confidence": 0.90,
    "sla": { "max_cost_usd": 0.05, "max_cycle_seconds": 120 }
  },
  "events": [                        // ordered spans, one per actor action
    { "id": "e1", "seq": 1, "actor": "recon-agent", "actor_type": "agent",
      "type": "agent.output", "attributes": { "confidence": 0.97, "amount": 4200, "...": "..." } },
    { "id": "e2", "seq": 2, "actor": "router",        "actor_type": "router", "type": "routing.decision", "attributes": { "route": "auto-post" } },
    { "id": "e3", "seq": 3, "actor": "posting-robot", "actor_type": "robot",  "type": "robot.input",      "attributes": { "amount": 4200, "...": "..." } },
    { "id": "e4", "seq": 4, "actor": "posting-robot", "actor_type": "robot",  "type": "robot.action",     "attributes": { "status": "success" } },
    { "id": "e5", "seq": 5, "actor": "system",        "actor_type": "system", "type": "run.metrics",      "attributes": { "cost_usd": 0.012, "cycle_seconds": 42 } }
  ]
}
```

The canonical event types are `agent.output`, `routing.decision`, `human.task`,
`human.decision`, `robot.input`, `robot.action`, and `run.metrics`. Event types
are free-form strings, so a new SUT can introduce its own.

## Evaluation pipeline

1. **Load** — `Trace.load()` parses and sorts events by `seq`;
   `load_contracts()` reads every contract in `contracts/`.
2. **Build the evaluation document** — for each contract, SeamProof assembles:
   - `handoff` — attributes of the event named by the contract's `handoff.source`
     (the payload crossing that boundary);
   - `context` — the trace's static context;
   - `events` — a flat view of every event (for `requires_event`);
   - `metrics` — the `run.metrics` attributes.
3. **Evaluate** — each assertion resolves its operands against the document and
   returns `passed`, a human-readable `detail`, and JSON `evidence`.
4. **Gate** — `evaluate_gate()` aggregates contract results. A failing
   **blocking** seam → NO-GO (exit 1). A failing **advisory** seam is reported
   but does not block (exit 0).
5. **Report** — one `GateResult` renders to `text`, `markdown`, `json`, or JUnit
   `xml`.

## Why a data-only contract language

Assertions read the evaluation document through a small reference/condition
language (`src/seamproof/expr.py`) with **no `eval` and no code execution**. A
trace is untrusted data; a contract is trusted policy. Keeping the boundary at
the data layer means a contract can be reviewed like a config file and a
malicious trace can never run code. See [SECURITY.md](../SECURITY.md).

## UiPath adapters

Two adapters connect the platform-neutral engine to UiPath Automation Cloud:

- **Ingest (input).** `ingest.py` normalises a Maestro **OpenTelemetry** (OTLP/JSON)
  export into a trace: each span becomes an event, typed OTLP attribute values
  (`stringValue`, `intValue`, `arrayValue`, `kvlistValue`, …) are decoded
  recursively, and a `run.context` span is lifted into the trace context. Exposed
  as `seamproof ingest` and `seamproof check --otel`.
- **Publish (output).** `publish.py` maps the `GateResult` onto the Test Manager
  result model and posts it. With the official `uipath` SDK installed it calls
  `uipath.platform.UiPath` (auth + org/tenant scoping handled by UiPath); without
  it, a stdlib REST transport uses `UIPATH_URL` + `UIPATH_ACCESS_TOKEN`. Exposed
  as `seamproof publish` (with `--dry-run` for an offline payload preview).

Both are testable offline against the bundled OTLP fixture and `--dry-run`, so the
only thing that needs a live tenant is the final POST.

## Module map

| Module | Responsibility |
| --- | --- |
| `trace.py` | Trace + Event model and accessors. |
| `expr.py` | Path references, reducers, and the condition tree. |
| `contracts.py` | Contract model and YAML/JSON loader. |
| `evaluators.py` | The assertion kinds and the per-contract evaluator. |
| `gate.py` | Severity-aware GO / NO-GO aggregation. |
| `report.py` | text / markdown / json / junit renderers. |
| `ingest.py` | UiPath Maestro OTLP export → SeamProof trace. |
| `publish.py` | Gate result → UiPath Test Manager (SDK or REST). |
| `cli.py` | `check`, `ingest`, `publish` subcommands and exit codes. |
