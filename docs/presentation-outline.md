# Presentation outline — SeamProof

Slide-by-slide outline + speaker notes for the deck (use the UiPath template; share
with "access to all"). ~10 slides, ~5 minutes.

## 1 · Title
**SeamProof — the seam tester for agentic processes.** Track 3 · UiPath Test Cloud.
Ankit Lade. github.com/ankitlade12/seamproof

## 2 · The problem
**Agents reach production only when we can govern them at scale.** An AI agent, an
RPA robot, and a human approver run in one flow — but we test each **in isolation**.
Production incidents come from the **seams between them**.
> Three failure modes: silent corruption (agent→robot), skipped checkpoint
> (routing→human), cost/SLA drift.

## 3 · The insight
**Test the seams, not just the actors.** A handoff is a *contract*; assert it
against the real run trace and gate the release. It's the QA layer for *composite*
agentic processes that agent evals and unit tests skip — and it fits UiPath uniquely
well (real robots + Action Center humans as first-class actors in one orchestrated flow).

## 4 · Architecture
Use **`docs/img/architecture.png`** — `[Agent] → [Router] → [Human] → [Robot]`
emitting an OTEL trace → **SeamProof** (trace → per-seam contracts → gate) → Test
Manager + CI.
> Decoupled by one artifact: the run trace.

## 5 · The three seams
Use **`docs/img/seams.png`**.

| Seam | Boundary | Catches |
| --- | --- | --- |
| seam-1 | agent→robot | `amount != sum(line_items)` (blocking) |
| seam-2 | routing→human | skipped approval (blocking) |
| seam-3 | process→finops | cost/cycle SLO drift (advisory) |

## 6 · Live demo — Seam 1 (the money shot) + the agent's fix
`uipath run process seam1_corruption` → `seamproof check` →
**GATE: NO-GO — expected 5400 == 4200, differs by 1200.**
> Valid JSON, wrong business outcome. The robot would post $5,400.

Then `seamproof check --recommend` → the **Seam Analyst** (an agent on the UiPath LLM
Gateway) returns the **root cause + concrete fix + fragility rating**. The tester is
itself an agent — Track 3's "agent that recommends fixes."
> It doesn't just *find* the broken seam; it tells you how to close it.

## 7 · Live demo — Seam 2 + the gate in Test Manager
$9,950 auto-posts around the human → NO-GO (seam-2). Show the **SeamProof** project
in Test Manager with the three seam test cases; the gate publishes Passed/Failed.

## 8 · Deep UiPath usage
Coded automation (`uipath run`, `@traced`) · **UiPath LLM Gateway** (recon agent **+
the Seam Analyst**) · **Action Center** human task · **`uipath eval`** (agent quality
= 1.0) · **OpenTelemetry** ingest · **Test Manager** v2 publish (real Finished
execution) · external **LangChain** agent on the UiPath Gateway (`uipath-langchain`).

## 9 · Built with a coding agent
Seam contracts, adversarial scenarios, and the reporter authored with **Claude Code**
through *UiPath for Coding Agents*. Low-code/coded agents do the work; the coding
agent writes the tests that guard the seams.

## 10 · Impact & close
Financial seam failures (wrong invoice posted, skipped approval) are exactly what
blocks agents from production. SeamProof is the release gate that catches them.
**Test the seams, not just the actors.**

---

### Speaker tips
- Lead with the red **NO-GO** on screen — it's the most memorable moment.
- Keep each live command pre-recorded as backup; the gate runs offline.
- Name the human's place in the flow explicitly (Action Center) — judges look for it.
