# Demo script — 5-minute run of show

Target: a tight problem → solution → live failure → gate arc. Times are guides.

## 0:00 – 0:40 · The problem

> "In an agentic process, an AI agent, an RPA robot, and a human approver run in
> one flow. We test each actor in isolation — the agent's eval here, the robot's
> test there. But production incidents come from the **seams between them**: the
> agent emits a valid-but-wrong number and the robot faithfully posts it; a
> boundary case routes around the human approval that policy required."

Show the architecture diagram ([architecture.md](architecture.md)). Name the
three actors and the two seams you'll break.

## 0:40 – 1:30 · The SUT, running

Show the invoice-exception process on **UiPath Automation Cloud**: the Agent
Builder recon agent, the Maestro routing, the Action Center approval task, the
Studio robot posting to the mock ERP. Run one **golden** invoice end-to-end so
the audience sees a clean run produce a trace.

```bash
seamproof check -c contracts -t examples/traces/golden_happy_path.json
```

> "Every run emits a trace. SeamProof reads the trace and tests the handoffs.
> Golden run — **GATE: GO**, 7 of 7 assertions pass."

## 1:30 – 2:45 · Break Seam 1 live (silent corruption)

Inject the failure: the agent returns valid JSON with a hallucinated total
(`amount: 5400`, line items still sum to `4200`). Re-run the gate:

```bash
seamproof check -c contracts -t examples/traces/seam1_amount_mismatch.json
```

> "Schema check passes — it's perfectly valid JSON. But the business outcome is
> wrong, and the robot would post `$5,400`. SeamProof asserts
> `amount == sum(line_items)` at the agent→robot seam and catches it:
> **expected 5400 == 4200, differs by 1200**. **GATE: NO-GO — blocked by
> seam-1.**"

This is the money shot. Let the red `NO-GO` sit on screen.

## 2:45 – 3:45 · Break Seam 2 (skipped checkpoint)

> "Second seam: routing to the human. A `$9,950` invoice sits in the review band.
> Output variability routes it straight to auto-post — around the approval policy
> required."

```bash
seamproof check -c contracts -t examples/traces/seam2_skipped_approval.json
```

> "SeamProof asserts that when policy demands a human, an approved decision must
> appear in the trace before the robot posts. It's missing. **GATE: NO-GO —
> blocked by seam-2.** The dangerous case can't auto-complete past us."

## 3:45 – 4:20 · The gate, where it lives

Show the JUnit report feeding **Test Manager** / CI:

```bash
seamproof check -c contracts -t examples/traces/seam1_amount_mismatch.json -f junit -o report.xml
```

> "The gate is a non-zero exit code and a JUnit report, so it drops natively into
> Test Manager or any CI pipeline. A change that breaks a seam blocks the
> release — automatically."

## 4:20 – 5:00 · Coding agent + close

> "The seam contracts, the adversarial scenarios, and the report generator were
> authored with a coding agent — Claude Code via UiPath for Coding Agents —
> from the process definition." (Show `.agent/EVALS.md` and one generated
> contract.)
>
> "SeamProof is the missing QA layer for composite agentic processes: not the
> agent, not the app, but the connective tissue. Test the seams, not just the
> actors."

## Backup plan

Record a clean take of each `seamproof check` run in advance (Day 3). If the live
SUT misbehaves on camera, narrate over the recorded gate output — the engine runs
offline from the bundled traces, so the gate demo never depends on the cloud.
