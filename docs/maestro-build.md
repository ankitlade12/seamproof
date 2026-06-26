# Building the system under test on UiPath Maestro

A step-by-step guide to building the invoice-exception process in your hackathon
tenant (`staging.uipath.com/hackathon26_1024`), wired so its run trace flows into
SeamProof. Ship a **thin, convincing slice**: one process, the two must-have
seams, a clear gate.

> What I can and can't do: I can't click inside your authenticated portal, so the
> UI steps are yours to execute. Everything paste-ready (agent prompts, schemas,
> test invoices, routing logic) lives in [`../sut/`](../sut/). Each phase ends with
> a **✅ checkpoint** and a **🔌 SeamProof** note telling you what the step must
> emit so the gate can read it.

## The shape

```
[Recon Agent] ──► [Gateway] ──► [User Task: approve] ──► [Robot: post] ──► End
 Agent Builder     route on        Action Center           Studio Web
 (agent.output)    amount/conf      (human.decision)        (robot.input/action)
```

Each box becomes a span in the Maestro trace. SeamProof asserts the contracts in
[`../contracts/`](../contracts/) across the seams between them.

## Phase 0 — Confirm the apps are on

From the portal's apps grid (top-left ⊞) confirm you can open: **Studio (Web)**,
**Agents** (Agent Builder), **Maestro**, **Orchestrator**, and — critically for
Track 3 — **Test Manager / Test Cloud**. Also confirm Orchestrator has a
**DefaultTenant** with at least one **robot + machine** (the Robot Task needs an
execution identity).

- ✅ **Checkpoint:** all five apps open without a "request access" wall, and
  Orchestrator → Tenant → Machines shows a usable machine.
- If Test Manager is missing, chase that first — it's the Track 3 target.

## Phase 1 — Build the recon agent (Agent Builder)

Docs: [Building an agent in Agent Builder](https://docs.uipath.com/agents/automation-cloud/latest/user-guide/building-an-agent-in-agent-builder),
[Prompts and arguments](https://docs.uipath.com/agents/automation-cloud/latest/user-guide/prompts-arguments-agent-builder).

1. **Agents → New agent** → name it `recon-agent`.
2. **Data Manager → Input schema → Edit raw schema** → paste the `input` object
   from [`../sut/agent/schemas.json`](../sut/agent/schemas.json).
3. **Output schema → Edit raw schema** → paste the `output` object from the same
   file. (Field names must stay exactly: `vendor_id`, `amount`, `currency`,
   `line_items[].amount`, `confidence`, `exception_flagged`.)
4. **Prompt tab** → paste the system prompt and user prompt from
   [`../sut/agent/recon-agent.md`](../sut/agent/recon-agent.md). Pick any
   available model (Claude Sonnet is a good default).
5. **Test** the agent with the `golden` case from
   [`../sut/data/invoices.json`](../sut/data/invoices.json).

- ✅ **Checkpoint:** for `golden`, the agent returns `amount: 4200`, two
  `line_items` summing to 4200, `confidence ≥ 0.9`, `exception_flagged: false`.
  For `seam1_corruption`, it returns `amount: 5400` with line items still summing
  to 4200 (it reports the *printed* total — that's the point).
- 🔌 **SeamProof:** this output is the `agent.output` span. `seam-1` reads
  `handoff.amount` vs `sum(handoff.line_items[*].amount)`; `seam-2` reads
  `handoff.confidence` and `handoff.amount`.

## Phase 2 — Model the process (Maestro / Studio Web)

Docs: [Model your process](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/model-your-process),
[Understanding process implementation](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/understanding-process-implementation).

1. **Maestro → New agentic process** → `invoice-exception-handling`.
2. On the canvas, lay out the BPMN:
   - **Start event**
   - **Service Task** → `Reconcile` (binds to the recon agent)
   - **Exclusive Gateway** → `Route`
   - **User Task** → `Approve` (Action Center) on the "needs review" branch
   - **Service/Robot Task** → `Post invoice` (binds to the RPA automation)
   - **End event**
3. Wire the gateway: "needs review" branch → `Approve` → `Post invoice`;
   "auto-post" branch → `Post invoice` directly.

- ✅ **Checkpoint:** the diagram validates with no dangling nodes; both gateway
  branches converge on `Post invoice`.

## Phase 3 — Implement and bind

1. **Process variables** — add the policy from `context` in
   [`../sut/data/invoices.json`](../sut/data/invoices.json):
   `auto_post_ceiling = 10000`, `human_review_floor = 9000`,
   `min_confidence = 0.90`, plus the vendor master and SLO. SeamProof reads these
   from the trace `context` (or you supply them via `--context` at gate time).
2. **Service Task `Reconcile`** — bind to `recon-agent`; map the invoice/po/receipt
   inputs and capture the structured output into process variables.
3. **Gateway `Route`** — condition for the **needs-review** branch:
   ```
   amount >= human_review_floor  OR  confidence < min_confidence  OR  exception_flagged
   ```
   > 🎬 **Seam-2 demo switch:** to demonstrate `seam-2` catching a skipped
   > checkpoint, temporarily set this to use only the hard ceiling
   > (`amount >= auto_post_ceiling`). Now the `9,950` case auto-posts around the
   > human — exactly the boundary-case bug SeamProof is built to catch. Restore the
   > correct condition afterwards.
4. **User Task `Approve`** — assign to a Manager/approver; the task records the
   decision. Docs: [Action Center tasks](https://docs.uipath.com/action-center/automation-cloud/latest/user-guide/about-tasks).
   - 🔌 **SeamProof:** this is the `human.decision` span; `seam-2` asserts an
     **approved** decision exists **before** the robot posts.
5. **Robot Task `Post invoice`** — bind to the posting automation (Phase 4).
   - 🔌 **SeamProof:** the inputs you pass here are the `robot.input` span that
     `seam-1` checks; the post result is `robot.action`.

## Phase 4 — The "ERP" the robot posts to

Keep it a mock for the demo. Easiest reliable options, pick one:

- **Studio Web automation + HTTP Request** to a throwaway echo endpoint
  (e.g. `https://httpbin.org/post`) — publish it, then bind the Robot Task to it.
- **Google Sheet** via the Google Workspace connector (append a row per invoice).
- **API Workflow** (new in this tenant — see the portal's "What's New") for a
  clean system-to-system call.

The robot just needs to record the posting and return a success status — the ERP
itself isn't what SeamProof tests; the `robot.input` / `robot.action` spans are.

- ✅ **Checkpoint:** running the automation standalone posts a row/echo and returns
  a success status.

## Phase 5 — Publish and run

Docs: [Publishing agentic processes](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/publishing-deploying-and-upgrading-agentic-processes).

1. **Publish** the process (name + changelog + version) to Orchestrator.
2. Run all three cases from `invoices.json`: `golden`, `seam1_corruption`,
   `seam2_near_ceiling` (with the gateway switch from Phase 3 for the last one).
3. Watch them in **Maestro → Monitor / All Instances**.

- ✅ **Checkpoint:** `golden` completes auto-posted; `seam1_corruption` posts
  `5,400`; `seam2_near_ceiling` auto-posts with no approval task.

## Phase 6 — Flow the run into SeamProof

The trace is what connects the live process to the gate. Two ways to obtain it:

**A. OpenTelemetry export (the clean path).** Configure OTEL export
([Configuring OpenTelemetry](https://docs.uipath.com/automation-cloud/automation-cloud/latest/admin-guide/configuring-opentelemetry),
[Agent traces](https://docs.uipath.com/agents/automation-cloud/latest/user-guide/agent-traces))
to a collector, save the OTLP/JSON for a run, then:

```bash
seamproof check -c contracts --otel run.otlp.json
```

**B. Assemble a trace from the instance view (the reliable path).** Open the run
in Maestro → All Instances, read the agent output, routing decision, robot
input/action, and run metrics, and drop them into a trace JSON shaped like
[`../examples/traces/golden_happy_path.json`](../examples/traces/golden_happy_path.json):

```bash
seamproof check -c contracts -t run.json
```

Then publish the verdict to Test Manager:

```bash
export UIPATH_URL=https://staging.uipath.com
export UIPATH_ACCESS_TOKEN=…            # from a Test Manager / external-app token
export UIPATH_ORGANIZATION_ID=hackathon26_1024
export UIPATH_TENANT_NAME=DefaultTenant
export UIPATH_PROJECT_ID=…              # your Test Manager project
seamproof publish -c contracts -t run.json --dry-run   # preview, then drop --dry-run
```

- ✅ **Done:** `golden` → **GATE: GO**; `seam1_corruption` → **NO-GO (seam-1)**;
  `seam2_near_ceiling` → **NO-GO (seam-2)**. That's the money shot: a real Maestro
  run, gated at the seams, blocking the release in Test Manager.

## Save the exports to the repo

Export the published process, the agent, and the RPA automation into
[`../sut/maestro/`](../sut/maestro/), [`../sut/agent/`](../sut/agent/), and
[`../sut/rpa/`](../sut/rpa/) so the submission repo contains the actual UiPath
project, per the hackathon's GitHub requirement.
