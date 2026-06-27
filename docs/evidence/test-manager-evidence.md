# Evidence — gate result in UiPath Test Manager

This is a **live result** that `seamproof publish` posted into UiPath Test Manager on
the hackathon tenant, fetched back **straight from the Test Manager v2 API** (so it's
the data Test Manager stores, not a local mock). The raw API response is committed
next to this file: [`test-manager-result.json`](test-manager-result.json).

- **Tenant:** `staging.uipath.com/hackathon26_1024/DefaultTenant`
- **Project:** SeamProof — `ccf142e8-a2e0-0000-d884-0b49d0877f68`
- **Execution:** `23b437f1-5e13-0c00-f010-0b49d10264cd`
- **Open in UI:** [test-executions/23b437f1…](https://staging.uipath.com/hackathon26_1024/DefaultTenant/testmanager_/#/projects/ccf142e8-a2e0-0000-d884-0b49d0877f68/executions/23b437f1-5e13-0c00-f010-0b49d10264cd)

## Execution

| Field | Value |
| --- | --- |
| Name | **SeamProof — invoice-exception-handling (NO-GO)** |
| Description | Gate NO-GO for trace `sut-seam1-001`: 6/7 checks passed |
| Source | `TestManager` |
| Test set | `5726c56c-d65f-0300-4690-0b49d1026440` (`SEAM:13`) |
| Started / finished | `2026-06-27T00:17:09Z` → `2026-06-27T00:17:14Z` |
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
  --testcase-map "seam-1=e1fb93a3…,seam-2=ba906c4c…,seam-3=3bbd1ef8…"
# -> Published to Test Manager — execution 23b437f1… (gate NO-GO)
```

`$APP_TOKEN` is a client-credentials token from an **External Application** with the
`TM.TestExecutions` scope (see [`../publish-to-test-manager.md`](../publish-to-test-manager.md)).

## Notes

- The execution-level `status` field reads `Running` in the raw JSON: the preview v2
  API leaves a manual test-case log's `executionEnd` open, so it never flips the
  rollup string. It does **not** affect the recorded outcome — the per-case results
  (`Failed` / `Passed` / `Passed`) and the `passed: 2, failed: 1` counts are final and
  are what's shown above.
- Viewing this in the Test Manager **UI** requires a Test Manager (Testing) **named-user
  license** on the tenant; the hackathon staging tenant's pool doesn't include one, so
  the UI shows an `unauthorized?hasRequiredLicense` page for the user even with the
  Tenant Administrator role. The integration itself is unaffected — the API wrote and
  read these results with the External Application's credentials.
