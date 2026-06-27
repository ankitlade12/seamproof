# Demo script — 5-minute run of show

A tight problem → live failure → **the agent recommends the fix** → gate arc, built
entirely on commands that work today (the coded automation runs on the UiPath runtime;
the gate runs offline). Total is budgeted to **5:00 exactly** — the hackathon hard cap.
Record a clean take of each command in advance as backup.

> **Recording it?** See [demo-recording-kit.md](demo-recording-kit.md) — a verified,
> offline-first runbook (TYPE → SCREEN → SAY per beat) so nothing breaks on camera.

**Prep:** run `uipath auth` and export `UIPATH_URL` + `UIPATH_ACCESS_TOKEN` so
`--recommend` runs on the **LLM Gateway** (offline it falls back to a deterministic
heuristic of identical shape, so the take looks the same either way).

| Beat | Time | Budget |
| --- | --- | --- |
| The problem | 0:00 – 0:30 | 30s |
| A real UiPath solution, running | 0:30 – 1:10 | 40s |
| Break Seam 1 (silent corruption) | 1:10 – 2:10 | 60s |
| **The Seam Analyst recommends the fix** | 2:10 – 2:55 | 45s |
| Break Seam 2 (skipped checkpoint) | 2:55 – 3:35 | 40s |
| Agent quality + cross-platform | 3:35 – 4:10 | 35s |
| The gate in Test Manager | 4:10 – 4:45 | 35s |
| Close | 4:45 – 5:00 | 15s |

## 0:00 – 0:30 · The problem

Show the architecture diagram ([architecture.md](architecture.md)).

> "The value of agents now is in **governing them at scale**. In an agentic process an
> AI agent, an RPA robot, and a human approver run in one flow — and we test each actor
> in isolation. But production incidents come from the **seams between them**: the agent
> emits a valid-but-wrong number and the robot faithfully posts it. SeamProof is the
> release gate that tests the handoffs — for any agent → robot → human process."

## 0:30 – 1:10 · A real UiPath solution, running

```bash
cd sut/automation
uipath run process '{"case": "golden"}'                       # runs on the UiPath runtime, traced
seamproof check -c ../../contracts --otel golden.otlp.json    # GATE: GO
```

> "This is a real UiPath **coded automation** — agent reconciles, router decides, human
> approves, robot posts — every step traced with `@traced`, the recon agent on the
> UiPath LLM Gateway. It emits OpenTelemetry; SeamProof gates a clean run: **GO**."

## 1:10 – 2:10 · Break Seam 1 live (silent corruption)

```bash
# use_llm:true runs recon on the REAL UiPath LLM Gateway (the AI Trust Layer)
uipath run process '{"case": "seam1_corruption", "use_llm": true}'
seamproof check -c ../../contracts --otel seam1_corruption.otlp.json
```

> "A real agent on the UiPath LLM Gateway extracts **$5,400** — valid JSON, but the
> line items sum to $4,200; the robot would post a $1,200 overpayment. SeamProof asserts
> `amount == sum(line_items)` at the agent→robot seam: **expected 5400 == 4200, differs
> by 1200. GATE: NO-GO, blocked by seam-1.**"

Let the red NO-GO sit on screen — this is the money shot.

## 2:10 – 2:55 · The Seam Analyst recommends the fix  ⭐

```bash
seamproof check -c ../../contracts --otel seam1_corruption.otlp.json --recommend
```

> "And the gate doesn't stop at *no*. `--recommend` runs the **Seam Analyst** — an agent
> on the UiPath LLM Gateway — which reads the failed seam and hands back a **root cause**
> and a **concrete fix**: *recompute the total from the source before the robot posts, or
> add a reconciliation post-condition* — and rates the seam **high fragility**. This is
> Track 3's ask: the tester is itself an agent. It finds the break **and** tells you how
> to close it."

This is the differentiator beat — keep the recommendation on screen.

## 2:55 – 3:35 · Break Seam 2 (skipped checkpoint)

```bash
uipath run process '{"case": "seam2_near_ceiling"}'           # $9,950 auto-posts around the human
seamproof check -c ../../contracts --otel seam2_near_ceiling.otlp.json
```

> "A $9,950 invoice in the review band auto-posts **around** the approval policy
> required. SeamProof asserts an approved human decision must precede the post — it's
> missing. **NO-GO, blocked by seam-2.**"

## 3:35 – 4:10 · Agent quality + cross-platform

```bash
uipath eval extract evaluations/eval-sets/recon.json --no-report   # recon quality: all 1.0
uipath run process '{"case": "seam1_corruption", "use_langchain": true}'   # external agent, same gate
```

> "`uipath eval` tests the agent in isolation — extraction scores 1.0; SeamProof tests
> the seams around it. And the recon agent can run as an external **LangChain** agent
> through the UiPath LLM Gateway — same gate, same NO-GO. Different jobs, one platform."

## 4:10 – 4:45 · The gate in Test Manager

Show the **SeamProof** project in Test Manager — the **Finished** execution, seam-1 the
failure (2 passed · 1 failed).

```bash
seamproof publish -c ../../contracts --otel seam1_corruption.otlp.json \
  --base-url $UIPATH_URL --project <PROJECT_ID> --recommend    # posts the gate result + prints the fix
```

> "The seams live in Test Manager as managed test cases; the gate publishes a
> **Finished** execution with Passed/Failed per seam — seam-1 the failure. A change that
> breaks a seam blocks the release." (Evidence: [docs/evidence/test-manager-evidence.md](evidence/test-manager-evidence.md).)

## 4:45 – 5:00 · Close

> "SeamProof is the QA layer for composite agentic processes — not the agent, not the
> app, but the connective tissue. The seams, the tests, and the Seam Analyst were
> authored with a coding agent through UiPath for Coding Agents. **Test the seams, not
> just the actors.**"

## Backup plan

Every `uipath run` / `seamproof check` was recorded in advance. The gate (and
`--recommend`'s heuristic fallback) run **offline** from the bundled OTLP, so the demo
never depends on the cloud being up. If you run long, the cut beat is *3:35 – 4:10*
(agent quality + cross-platform) — drop it to recover 35s without losing the core arc.
