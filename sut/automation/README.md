# Invoice-exception process — UiPath coded automation

A real **UiPath coded automation** (`uipath.json` + a dataclass entrypoint, the
same shape `uipath new` scaffolds) that implements the invoice-exception process
SeamProof tests. It's the runnable, code-first counterpart to the low-code Maestro
build in [`../../docs/maestro-build.md`](../../docs/maestro-build.md).

## What makes it "UiPath"

- **Coded automation** declared in [`uipath.json`](uipath.json); runs with
  `uipath run`.
- Every step is wrapped in UiPath's **`@traced`** decorator, so a tenant run emits
  native UiPath/Maestro spans.
- The recon step calls the **UiPath LLM Gateway** (`UiPath().llm.chat_completions`,
  the AI Trust Layer) when `use_llm` is set and credentials are present.
- The human step creates a real **Action Center** task (`UiPath().tasks.create`)
  when `use_action_center` is set.
- The recon agent is quality-tested the UiPath-native way with **`uipath eval`**
  (see [Evaluate the recon agent](#evaluate-the-recon-agent)).
- It emits an **OpenTelemetry** (OTLP/JSON) document of the run that SeamProof
  ingests — closing the agent → ingest → gate → publish loop.

It degrades gracefully offline: no credentials → deterministic recon, no-op
tracing, OTLP still written. So the whole pipeline is demonstrable with zero
tenant access, then lights up fully in the tenant.

## Run it

In the tenant (real UiPath traces + LLM Gateway):

```bash
uipath auth
uipath run process '{"case": "seam1_corruption", "use_llm": true}'
```

Offline (deterministic, writes an OTLP file SeamProof can gate):

```bash
cd sut/automation
python main.py seam1_corruption          # -> seam1_corruption.otlp.json
seamproof check -c ../../contracts --otel seam1_corruption.otlp.json   # NO-GO (seam-1)
```

## Cases

| `case` | Routing | SeamProof verdict |
| --- | --- | --- |
| `golden` | auto-post | **GO** |
| `high_value` | human review → approved (Action Center) | **GO** |
| `seam1_corruption` | auto-post | **NO-GO** — seam-1 (`amount 5400 != Σ line_items 4200`) |
| `seam2_near_ceiling` | auto-post via a ceiling-only gateway bug | **NO-GO** — seam-2 (skipped human approval) |

Add `"use_action_center": true` to create a real Action Center task at the human
step (tenant + `uipath auth` required), e.g.
`uipath run process '{"case": "high_value", "use_action_center": true}'`.

## Evaluate the recon agent

The recon agent is quality-tested with a native **`uipath eval`** set
([`evaluations/`](evaluations/)) that scores its structured extraction against an
expected output with a JSON-similarity evaluator:

```bash
uipath eval extract evaluations/eval-sets/recon.json --no-report
```

All three extraction cases score `1.0`. This is the agent-quality counterpart to
SeamProof's seam tests: `uipath eval` checks the agent in isolation, SeamProof
checks the handoffs around it.

## Cross-platform note

`reconcile()` is provider-agnostic: swap the deterministic/UiPath-LLM extractor
for an external **LangChain** agent and the rest of the automation — routing,
human task, robot post, and OTLP emission — is unchanged. That external-agent
path is what targets the Most Innovative Cross-Platform Integration award.
