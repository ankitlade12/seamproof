# Evidence — gate result in UiPath Test Manager

This is a **live result** that `seamproof publish` posted into UiPath Test Manager on
the hackathon tenant, fetched back **straight from the Test Manager v2 API** (so it's
the data Test Manager stores, not a local mock). The raw API response is committed
next to this file: [`test-manager-result.json`](test-manager-result.json).

- **Tenant:** `staging.uipath.com/hackathon26_1024/DefaultTenant`
- **Project:** SeamProof — `ccf142e8-a2e0-0000-d884-0b49d0877f68`
- **Execution:** `140a2ed2-af13-0c00-957d-0b49d1761ea2`
- **Open in UI:** [executions/140a2ed2…](https://staging.uipath.com/hackathon26_1024/DefaultTenant/testmanager_/#/projects/ccf142e8-a2e0-0000-d884-0b49d0877f68/executions/140a2ed2-af13-0c00-957d-0b49d1761ea2)

## Execution

| Field | Value |
| --- | --- |
| Name | **SeamProof — invoice-exception-handling (NO-GO)** |
| Description | Gate NO-GO for trace `sut-seam1-001`: 6/7 checks passed |
| Source | `TestManager` |
| Test set | `4665533d-e15f-0300-9213-0b49d1761dd7` (`SEAM:14`) |
| Started / finished | `2026-06-27T14:05:34Z` → `2026-06-27T14:05:41Z` |
| Status | **Finished** |
| **Result** | **passed 2 · failed 1** |

## Per-seam results (test-case logs)

One Test Manager test case per seam, with the result SeamProof set from the gate:

| Seam | What it guards | Severity | Test case | **Result** |
| --- | --- | --- | --- | --- |
| **seam-1** | agent→robot data: `amount == Σ line_items` | blocking | `e1fb93a3-d789-0a00-4bca-0b49d09488bb` | **Failed** |
| **seam-2** | routing→human checkpoint reached | blocking | `ba906c4c-d889-0a00-3ebc-0b49d094891e` | Passed |
| **seam-3** | cost / cycle-time SLO | advisory | `3bbd1ef8-d989-0a00-bfb8-0b49d0948992` | Passed |

**seam-1 failed** because the agent's reconciled `amount` (5400) did not equal the sum
of the line items (4200) — the silent corruption SeamProof exists to catch. That one
blocking failure is what drives the gate to **NO-GO**.

## How it was produced (reproducible)

```bash
# one clean run, end to end, through the published CLI
python sut/automation/main.py seam1_corruption run.otlp.json
seamproof publish -c contracts --otel run.otlp.json \
  --base-url https://staging.uipath.com/hackathon26_1024/DefaultTenant \
  --token "$APP_TOKEN" --project ccf142e8-a2e0-0000-d884-0b49d0877f68 \
  --testcase-map "seam-1=e1fb93a3…,seam-2=ba906c4c…,seam-3=3bbd1ef8…" --recommend
# -> Published to Test Manager — execution 140a2ed2… (gate NO-GO)
```

`$APP_TOKEN` is a client-credentials token from an **External Application** with the
`TM.TestExecutions` scope (see [`../publish-to-test-manager.md`](../publish-to-test-manager.md)).

## Notes

- Each per-seam log is **finished** (`testcaselogs/testexecution/{id}/finish`) once its
  result is set — that's what moves the execution to a terminal **`Finished`** status
  rather than leaving it on "Running". (Gotcha: `override-result` alone records the
  result but never ends the log, so the execution would otherwise stay "Running".)
- The user views this with **Tenant Administrator** access; full Test Manager *write*
  features need a Test Manager (Testing) **named-user license** the hackathon staging
  tenant doesn't include, so the UI runs in limited (view) mode. That's fine — SeamProof
  does all the writing via the API with the External Application's credentials; the UI
  is only for viewing the result.
- With `--recommend`, the **Seam Analyst**'s root-cause + fix print with the gate report
  at publish time. In this preview API a finished log supersedes its per-log reason, so
  the recommendation lives in the report / `check --recommend` rather than the Test
  Manager reason field.
