# Demo script — 5-minute run of show

A tight problem → live failure → gate arc, built entirely on commands that work
today (the coded automation runs on the UiPath runtime; the gate runs offline).
Times are guides. Record a clean take of each command in advance as backup.

## 0:00 – 0:35 · The problem

> "The value of agents now is in **governing them at scale**. In an agentic process
> an AI agent, an RPA robot, and a human approver run in one flow — and we test each
> actor in isolation. But production incidents come from the **seams between them**:
> the agent emits a valid-but-wrong number and the robot faithfully posts it; a
> boundary case routes around the human approval that policy required. SeamProof is
> the release gate that tests the handoffs — for any agent → robot → human process."

Show the architecture diagram ([architecture.md](architecture.md)).

## 0:35 – 1:20 · A real UiPath solution, running

The system under test is a **UiPath coded automation** ([sut/automation/](../sut/automation/)).

```bash
cd sut/automation
uipath run process '{"case": "golden"}'         # runs on the UiPath runtime, traced
```

> "This is a real UiPath coded automation — agent reconciles, router decides,
> human approves, robot posts — every step traced with UiPath's `@traced`, the
> recon agent on the UiPath LLM Gateway. It emits an OpenTelemetry trace."

Gate the clean run:

```bash
seamproof check -c ../../contracts --otel golden.otlp.json     # GATE: GO
```

## 1:20 – 2:35 · Break Seam 1 live (silent corruption)

```bash
# use_llm:true runs recon on the REAL UiPath LLM Gateway (the AI Trust Layer)
uipath run process '{"case": "seam1_corruption", "use_llm": true}'
seamproof check -c ../../contracts --otel seam1_corruption.otlp.json
```

> "A real agent on the UiPath LLM Gateway extracts $5,400 — valid JSON, but the
> business outcome is wrong; the robot would post $5,400.
> SeamProof asserts `amount == sum(line_items)` at the agent→robot seam:
> **expected 5400 == 4200, differs by 1200. GATE: NO-GO, blocked by seam-1.**"

Let the red NO-GO sit on screen — this is the money shot.

## 2:35 – 3:25 · Break Seam 2 (skipped checkpoint)

```bash
uipath run process '{"case": "seam2_near_ceiling"}'            # $9,950 auto-posts around the human
seamproof check -c ../../contracts --otel seam2_near_ceiling.otlp.json
```

> "A $9,950 invoice in the review band auto-posts around the approval policy
> required. SeamProof asserts an approved human decision must precede the post —
> it's missing. **NO-GO, blocked by seam-2.**"

## 3:25 – 4:05 · Test the agent the UiPath-native way + cross-platform

```bash
uipath eval extract evaluations/eval-sets/recon.json --no-report   # recon quality: all 1.0
```

> "`uipath eval` tests the agent in isolation — extraction quality scores 1.0.
> SeamProof tests the seams around it. Different jobs."

```bash
uipath run process '{"case": "seam1_corruption", "use_langchain": true}'
```

> "And the recon agent can run as an external **LangChain** agent through the
> UiPath LLM Gateway — same gate, same result."

## 4:05 – 4:45 · The gate in Test Manager

Show the **SeamProof** project in Test Manager with the three seam test cases
(`seam-1`, `seam-2`, `seam-3`).

```bash
seamproof publish -c ../../contracts --otel seam1_corruption.otlp.json \
  --base-url $UIPATH_URL --project <PROJECT_ID>      # posts the gate result
```

> "The seams live in Test Manager as managed test cases; the gate publishes
> Passed/Failed per seam. A change that breaks a seam blocks the release."

## 4:45 – 5:00 · Close

> "SeamProof is the missing QA layer for composite agentic processes — not the
> agent, not the app, but the connective tissue. The seam contracts and tests were
> authored with a coding agent. **Test the seams, not just the actors.**"

## Backup plan

Every `uipath run` / `seamproof check` was recorded in advance. The gate runs
offline from the bundled OTLP, so the demo never depends on the cloud being up.
