# Community Forum use case — SeamProof

Draft for the UiPath Community Forum use-case post finalists publish. Tone: share
the idea and how it was built so others can reuse it.

---

**Title:** SeamProof — testing the *seams* between agents, robots, and humans

**Category:** Agentic Automation / Testing (Test Cloud)

## Overview

SeamProof is a release gate for agentic processes. Instead of testing the AI agent,
the robot, and the human approver in isolation, it tests the **handoffs between
them** — the seams where production incidents actually happen — and blocks a release
when a handoff breaks.

Repo: https://github.com/ankitlade12/seamproof (Apache-2.0)

## The problem

In a real agentic process an AI agent, an RPA robot, and a human run in one flow. We
test each actor on its own, but the failures that reach production live in the
connective tissue:

- the agent returns valid JSON with a wrong number, and the robot faithfully posts it;
- a boundary case routes around the human approval that policy required;
- a model change quietly doubles cost-per-run.

A schema check passes; the business outcome is wrong.

## The approach

Treat every handoff as a **contract** and assert it against the real run trace:

- **Seam 1 — Agent → Robot:** `amount == sum(line_items)`, currency matches the PO,
  vendor is approved.
- **Seam 2 — Routing → Human:** when policy requires a human, an approved decision
  must exist *before* the robot posts.
- **Seam 3 — Cost / cycle SLO:** advisory, reports drift without blocking.

The contracts are plain YAML (data-only, no code execution), evaluated over an
OpenTelemetry trace of the run, producing a **GO / NO-GO** gate with the evidence.

## How it's built on UiPath

- The system under test is a **UiPath coded automation** (`uipath` Python SDK) — a
  recon **agent** (UiPath LLM Gateway, or an external **LangChain** agent via
  `uipath-langchain`), a router, an **Action Center** human task, and a posting
  **robot** — every step `@traced`, emitting OpenTelemetry.
- **`uipath eval`** quality-tests the recon agent in isolation; SeamProof tests the
  seams around it.
- The gate result publishes to **Test Manager** (v2 REST) as a test execution with a
  Passed/Failed result per seam.
- It also runs offline from a bundled OTLP fixture, so the whole pipeline is
  demonstrable without a tenant and lights up fully in one.

## Result

A change that breaks a seam returns a non-zero gate and blocks the release — e.g.
`expected 5400 == 4200, differs by 1200 → GATE: NO-GO (seam-1)`. The three seams live
in Test Manager as managed test cases.

## Reuse it

Point `seamproof check` at any run trace in the documented shape (a Maestro OTEL
export maps directly). Write your own seam contracts for your process — the format is
in `docs/seam-contracts.md`. Feedback and contributions welcome.
