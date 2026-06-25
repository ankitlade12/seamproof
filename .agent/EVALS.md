# Agent guide — authoring seams with a coding agent

This file is the working brief for a **coding agent** (e.g. Claude Code via
*UiPath for Coding Agents*) operating in this repo. SeamProof's contracts,
scenarios, and report logic are designed to be *generated and maintained by a
coding agent* from a process definition — this file tells the agent how.

> Low-code vs. coding agents: the **system under test** is built with UiPath
> low-code agents (Agent Builder), robots (Studio), and human steps (Action
> Center). **SeamProof itself** — the tester — is authored with a coding agent.
> See the README section "Coding agents vs. low-code agents" for the full split.

## What the agent owns

1. **Seam contracts** (`contracts/*.yaml`) — from the process definition, derive
   the invariants the *receiving* actor at each boundary depends on.
2. **Scenarios** (`scenarios/*.suite.yaml`) — for each seam, generate a golden
   trace and at least one adversarial trace that should trip exactly that seam.
3. **Report/gate wiring** (`src/seamproof/report.py`) — keep the renderers in
   sync when a new severity or output target is added.

## Contract schema (the only shape the agent should emit)

```yaml
id: seam-N                      # stable seam id
name: Human-readable seam name
description: One paragraph: what breaks here and why it matters.
severity: blocking | advisory   # advisory reports without gating
boundary: { from: <actor>, to: <actor> }
handoff:
  source: { type: <event-type> }  # which event carries the boundary payload
assertions:
  - id: <kebab-id>
    kind: equals | not_equals | in_set | matches | range | requires_event
    description: What this check guarantees.
    # ... kind-specific fields (see docs/seam-contracts.md)
```

Operands are data, never code:

- `{ ref: "handoff.amount" }` — a dotted path (`[*]` wildcard, `[0]` index).
- `{ ref: "handoff.line_items[*].amount", reduce: sum }` — fold a list.
- `{ const: 10000 }` or a bare literal.

## Generation procedure

1. Read the process definition and list every actor-to-actor boundary.
2. For each boundary, ask: *what does the receiver assume that it cannot verify?*
   Each assumption becomes one assertion.
3. Emit the contract. Prefer several small, named assertions over one broad one —
   named failures are what make the gate output legible.
4. Generate a golden trace (all pass) and one injected-failure trace per seam.
5. Register every trace in the scenario suite with its expected outcome.
6. Run `make check`. The scenario suite must be green and the
   `test_every_trace_is_covered` guard must pass.

## Guardrails

- Never introduce `eval`, `exec`, dynamic import, or shell-out into the
  evaluation path. Assertions are declarative by design.
- A contract change is a policy change: keep `description` fields accurate.
- Every new assertion kind needs a unit test in `tests/test_evaluators.py`.
