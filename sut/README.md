# System Under Test — invoice-exception handling

This folder holds the **system under test (SUT)**: the three-actor UiPath Maestro
process that SeamProof evaluates. SeamProof does not need the SUT to run in order
to demonstrate the engine — it works from the exported run traces in
[`../examples/traces/`](../examples/traces/) — but the SUT is what produces those
traces in production.

## Build it

Step-by-step build guide: [`docs/maestro-build.md`](../docs/maestro-build.md).
Paste-ready artifacts for the portal:

- [`agent/schemas.json`](agent/schemas.json) — Agent Builder input/output schemas.
- [`agent/recon-agent.md`](agent/recon-agent.md) — the agent's system/user prompts.
- [`data/invoices.json`](data/invoices.json) — the three test invoices (golden + one per seam).

## The process

A procure-to-pay slice with one agent, one robot, and one human:

| Step | Actor | UiPath component | Responsibility |
| --- | --- | --- | --- |
| 1. Reconcile | Recon agent | Agent Builder (or an external LangChain agent) | Read the invoice, match it to its PO and receipt, extract vendor/amount/currency/line-items, flag discrepancies, emit a confidence score. |
| 2. Route | Router | Maestro | Decide auto-post vs. human-review from amount, confidence, and exception flags. |
| 3. Approve | Human | Action Center | Approve or reject invoices that are exceptions or above the review threshold. |
| 4. Post | Posting robot | Studio (RPA) | Post the approved invoice to the ERP (a mock REST stub / Google Sheet for the demo). |

```
[Recon Agent] ──► [Router] ──► [Human (Action Center)] ──► [Posting Robot] ──► ERP
 Agent Builder     Maestro          approval task              Studio robot
```

## Layout

| Folder | Contents |
| --- | --- |
| `maestro/` | The Maestro process export (`.json` / package). |
| `agent/` | Agent Builder configuration, or the external LangChain agent. |
| `rpa/` | The Studio workflow that posts to the mock ERP. |

> The UiPath project exports are added here once the process is published on
> UiPath Automation Cloud. The trace schema they emit is documented in
> [`../docs/architecture.md`](../docs/architecture.md); any source that produces
> that schema (Maestro audit export, a LangChain callback handler, or a
> hand-authored fixture) can feed SeamProof.

## Producing a trace

Each run of the SUT emits a trace in the shape consumed by `seamproof check`.
Map the Maestro audit events onto the trace `events` array (`agent.output`,
`routing.decision`, `human.decision`, `robot.input`, `robot.action`,
`run.metrics`) and populate `context` with the PO, vendor master, ceilings, and
SLOs the run executed against.
