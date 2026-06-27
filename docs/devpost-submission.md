# Devpost submission — SeamProof

Paste-ready content for the Devpost project page. **Track 3 — UiPath Test Cloud.**

---

## Tagline

The seam tester for agentic processes — assert the agent → robot → human handoffs and gate the release.

## The problem (Inspiration)

In an agentic business process, an AI agent, an RPA robot, and a human approver run
together in one flow. But testing today validates each actor **in isolation** — the
agent's eval here, the robot's test there, the human step assumed correct. The
failures that actually cause production incidents emerge **at the seams between
actors**:

- **Agent → Robot (silent corruption):** the agent emits structurally valid but
  semantically wrong output (right JSON, wrong number) and the robot faithfully
  executes it. The schema check passes; the business outcome is wrong.
- **Routing → Human (skipped checkpoint):** output variability routes work *around*
  a human approval that policy required — the dangerous case auto-completes.
- **Non-functional (cost / SLA drift):** a prompt or model change quietly doubles
  cost-per-run or breaches the cycle-time SLO.

Isolated agent evals and unit tests never see these. They live in the connective
tissue. Concretely: in our reference case the agent reconciles an invoice to **$5,400**
when the line items sum to **$4,200** — a **$1,200 overpayment** in valid JSON that
posts to the ERP in under two seconds, no human in the loop. SeamProof blocks it at the
release gate.

## What it does

The hackathon's premise is that "the real value now lies in how we **operate and
govern agents at scale**." SeamProof is that governance layer for the release gate:
it treats every handoff as a **contract** and tests it against the real run trace,
asserting trace-level properties at each agent → robot → human boundary and emitting
a **go/no-go gate** with the evidence. A change that breaks a seam blocks the
release — automatically, in CI and Test Manager.

And the gate doesn't stop at *no*. The **Seam Analyst** — an agent on the UiPath **LLM
Gateway** (AI Trust Layer) — reads each failed seam and returns a **root cause**, a
**concrete fix**, and a **fragility** rating, written into the report and onto the
**Test Manager** result. So the tester itself is agentic, and it hits all four of Track
3's asks: it **validates** the AI-infused workflow, **recommends fixes**, **identifies
fragile** seams, and treats seam contracts as executable **requirements**.

The seam-contract model **generalises** to any agent → robot → human process; the
invoice-exception process is one reference implementation. And it fits UiPath
uniquely well: real robots and Action Center human tasks are first-class actors in one
orchestrated process — the exact shape SeamProof tests.

## How we built it

- **System under test** — a UiPath **coded automation** (`sut/automation/`) of an
  invoice-exception process: a recon **agent** (UiPath LLM Gateway, or an external
  **LangChain** agent), a router, an **Action Center** human approval, and a posting
  **robot**. Every step is wrapped in UiPath's `@traced`; the run is emitted as
  **OpenTelemetry**. It runs on the UiPath runtime via `uipath run`.
- **SeamProof engine** — a small, data-only contract language and trace evaluator
  (no `eval`, no code execution) with six assertion kinds and a severity-aware gate.
  It ingests the OTEL trace and renders text / markdown / JSON / JUnit, plus a
  non-zero exit code that gates CI.
- **Seam Analyst agent** — when a seam fails, an agent on the UiPath **LLM Gateway**
  returns a root cause + recommended fix + fragility rating (`check --recommend`),
  degrading to a deterministic heuristic offline. The fix is also attached to the
  Test Manager result, so the remediation lives next to the failure.
- **UiPath integration** — ingest Maestro/agent **OpenTelemetry** traces; publish the
  gate result to **Test Manager** via its v2 REST API (test cases + execution +
  per-seam results); quality-test the agent with **`uipath eval`**.
- **Authored with a coding agent** — the seam contracts, adversarial scenarios, and
  report generator were written with **Claude Code** through *UiPath for Coding
  Agents* (the bonus criterion).

## UiPath components used

UiPath Automation Cloud · Maestro (orchestration + OTEL traces) · Agent Builder /
Coded Agents (Python SDK) · UiPath LLM Gateway (AI Trust Layer — recon agent + the
Seam Analyst) · Action Center (human task) · Studio/RPA (posting robot) · Test Cloud /
Test Manager (gate results)
· `uipath` CLI + `uipath eval` · `uipath-langchain` (LangChain on the UiPath
Gateway) · UiPath for Coding Agents.

## Coding agents vs. low-code agents (required clarification)

Both, deliberately. The **system under test** ships as a real, runnable **coded**
automation (`uipath` Python SDK, runs via `uipath run`), plus **paste-ready low-code
artifacts** (an Agent Builder agent spec + schemas in `sut/agent/`) to build the same
process in Maestro. **SeamProof itself — the tester** — is authored with a **coding
agent** (Claude Code) through *UiPath for Coding Agents*. In short: low-code/coded
agents *do the work*; the coding agent *writes the tests that guard the seams between
them*.

## Challenges

- Test Manager has no public "post external results" doc; we reverse-engineered the
  real **v2 REST API** from the tenant's live Swagger and matched it exactly.
- Making the whole pipeline demonstrable **offline** (no tenant) while lighting up
  fully in the tenant — solved with graceful fallbacks and a bundled OTLP fixture.

## Accomplishments

- A working, tested engine (74 passing tests, CI green on every push) that gates real
  UiPath runs and catches all three seam failures.
- A genuine UiPath coded automation that runs via `uipath run`, with `@traced`,
  LLM Gateway, Action Center, `uipath eval`, and an external LangChain agent.
- The gate's seams created as managed test cases in a real Test Manager project, with
  a **Finished** execution carrying the per-seam Passed/Failed results — captured back
  from the API in [`evidence/test-manager-evidence.md`](evidence/test-manager-evidence.md).
- A **Seam Analyst** agent that turns a red gate into an actionable root-cause + fix,
  on the LLM Gateway, with the recommendation recorded on the Test Manager result.

## What's next

Auto-discover seams from a Maestro export · publish full executions via an External
Application scope · a web report UI · broader systems under test.

## Built with

`uipath` · python · maestro · agent-builder · action-center · test-manager ·
opentelemetry · langchain · claude-code

## Links

- **Repo:** https://github.com/ankitlade12/seamproof
- **Test Manager evidence:** [docs/evidence/test-manager-evidence.md](https://github.com/ankitlade12/seamproof/blob/main/docs/evidence/test-manager-evidence.md)
- **Demo video:** _(add link — record before submitting)_
- **Presentation:** _(add link — fill the provided template, share "access to all")_
