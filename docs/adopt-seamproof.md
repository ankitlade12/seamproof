# Adopt SeamProof for your own agentic process

SeamProof isn't invoice-specific. The engine gates *any* agent → robot → human process
from its run trace, so you can point it at your own Maestro process in three steps. This
is the reusable core the bundled invoice-exception process demonstrates.

## 1. Find your seams

Walk your process and mark every **handoff** where one actor depends on another's
output. Each is a candidate seam. The three that bite hardest in practice:

- **agent → robot** — the agent emits structurally valid but semantically wrong output
  and the robot executes it faithfully (the silent-corruption seam).
- **routing → human** — output variability lets a case route *around* a human approval
  that policy required (the skipped-checkpoint seam).
- **process → finops** — a prompt/model change quietly breaks a cost or cycle-time SLO
  (the non-functional seam — usually *advisory*).

## 2. Write one contract per seam

A contract is plain YAML: the boundary, where the handoff payload lives in the trace,
and the properties that must hold. No code, no `eval`. Copy this and edit:

```yaml
id: seam-1
name: Agent to Robot data contract
boundary: { from: your-agent, to: your-robot }
severity: blocking          # or 'advisory' to warn without gating
handoff:
  source: { actor: your-agent, type: agent.output }
assertions:
  - id: total-matches-source
    kind: equals             # equals | not_equals | in_set | matches | range | requires_event
    left:  { path: handoff.amount }
    right: { path: handoff.line_items[*].amount, reduce: sum }
    tolerance: 0.005
  - id: human-approval-when-required
    kind: requires_event
    when:  { path: handoff.amount, op: ">", value: 5000 }
    event: { actor_type: human, type: human.decision, where: { status: approved } }
    before: { type: robot.post }
```

The six assertion kinds and the path/reducer language are documented in
[seam-contracts.md](seam-contracts.md).

## 3. Get a trace and gate it

SeamProof reads a UiPath **OpenTelemetry** export (or its own trace JSON):

```bash
# straight from a Maestro/agent OTLP export — ingestion happens inline
seamproof check -c contracts/ --otel your_run.otlp.json

# add the Seam Analyst's root-cause + fix on any failure
seamproof check -c contracts/ --otel your_run.otlp.json --recommend
```

Non-zero exit on a blocking failure wires the gate into CI or a UiPath Test pipeline.
Publish the result to Test Manager with `seamproof publish` (see
[publish-to-test-manager.md](publish-to-test-manager.md)).

## That's it

Your process now has a release gate on its seams, and the Seam Analyst recommends a fix
when one breaks. If you build on this, share it on the **UiPath Community Forum** — the
goal is that seam-testing becomes a pattern anyone running composite agentic processes
can lift. Apache-2.0 licensed; PRs and new assertion kinds welcome.
