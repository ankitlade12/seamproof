# Publishing the gate result to UiPath Test Manager

`seamproof publish` posts the gate result into **UiPath Test Manager** as a
`ThirdParty` test execution with one Passed/Failed test-case log per seam. The
endpoints and payloads are the real Test Manager **v2** API, verified against the
tenant's live Swagger (`testmanager_/swagger/v2/swagger.json`).

> Status for the hackathon tenant: Test Manager **is enabled** on
> `staging.uipath.com/hackathon26_1024` (the swagger responds). What's left is the
> one thing only you can do — authenticate — plus pointing at a project.

## What it does (per run)

1. `POST testmanager_/api/v2/{projectId}/testcases` — one test case per seam (only if you don't supply existing ids)
2. `POST .../testexecutions` — a `ThirdParty` execution named `SeamProof — <process> (GO|NO-GO)`
3. `POST .../testcaselogs` — a log per seam, linked to the execution
4. `POST .../testcaselogs/{id}/override-result` — sets each result `Passed`/`Failed`, with the seam's failure detail as the reason
5. `POST .../testexecutions/{id}/finish`

## Step 1 — Authenticate (only you can do this)

From any UiPath project dir (e.g. `sut/automation/`):

```bash
uipath auth     # opens the browser; sign in to staging.uipath.com / hackathon26_1024
```

This stores the session the `uipath` SDK reads, so you don't paste tokens.

## Step 2 — Get a project (and a place to put the test cases)

In Test Manager, create a project (or use an existing one) and note its **project
id** (it's in the URL). Then choose one of:

- **Auto-create the test cases** — grab a **section id** from the project and pass
  `--container <sectionId>`; SeamProof creates the three seam test cases for you.
- **Reuse existing test cases** — create three test cases (one per seam, set their
  Automation ID to `seam-1`, `seam-2`, `seam-3`) and pass their ids with
  `--testcase-map`.

## Step 3 — Preview, then publish

Always dry-run first — it prints the exact request plan and sends nothing:

```bash
seamproof check  -c contracts --otel run.otlp.json          # produce/gate a trace
seamproof publish -c contracts --otel run.otlp.json \
  --base-url https://staging.uipath.com \
  --org hackathon26_1024 --tenant DefaultTenant \
  --project <PROJECT_ID> --container <SECTION_ID> --dry-run
```

When the plan looks right, drop `--dry-run`:

```bash
seamproof publish -c contracts --otel run.otlp.json \
  --base-url https://staging.uipath.com \
  --org hackathon26_1024 --tenant DefaultTenant \
  --project <PROJECT_ID> --container <SECTION_ID>
# -> Published to Test Manager — execution <id> (gate NO-GO)
#    https://staging.uipath.com/hackathon26_1024/DefaultTenant/testmanager_/#/projects/<PROJECT_ID>/test-executions/<id>
```

Reusing pre-created test cases instead of `--container`:

```bash
seamproof publish -c contracts --otel run.otlp.json \
  --base-url https://staging.uipath.com --org hackathon26_1024 --tenant DefaultTenant \
  --project <PROJECT_ID> \
  --testcase-map "seam-1=<id>,seam-2=<id>,seam-3=<id>"
```

## Auth notes

- With the `uipath` SDK installed (`pip install "seamproof[uipath]"`) and `uipath
  auth` done, publishing uses the SDK transport and the auth session — no token on
  the command line.
- Without the SDK, set `UIPATH_ACCESS_TOKEN` (and `UIPATH_URL`) and SeamProof uses
  a stdlib REST call instead.
- `UIPATH_URL` / `UIPATH_ORGANIZATION_ID` / `UIPATH_TENANT_NAME` / `UIPATH_PROJECT_ID`
  are read from the environment if you omit the matching flags.

## Permissions (important)

Creating test **cases** works with the scopes `uipath auth` grants
(`TM.TestCases`, `TM.TestSets`, `TM.Requirements`). Creating a test **execution /
results** needs a test-execution scope the interactive login does **not** include —
a direct `seamproof publish` reaches `POST .../testexecutions` and returns **403**
with a normal user token (verified on the hackathon tenant).

To post results, use an **External Application** (client credentials) with the full
Test Manager scopes:

1. **Automation Cloud → Admin → External Applications → Add Application** →
   *Confidential application*.
2. **Add scopes → Test Manager** → select the Test Manager API scopes (include the
   **test execution / results** scopes, not just `TM.TestCases`). Save.
3. Copy the **App ID** (client id) and **App Secret**.
4. Authenticate unattended (no browser):

   ```bash
   uipath auth --base-url https://staging.uipath.com/hackathon26_1024/DefaultTenant \
     --client-id <APP_ID> --client-secret <APP_SECRET> --scope "TM ..."
   ```

5. Run the publish — it now reaches `POST .../testexecutions` with permission and the
   full v2 flow (execution → logs → results → finish) completes:

   ```bash
   seamproof publish -c contracts --otel run.otlp.json \
     --base-url https://staging.uipath.com/hackathon26_1024/DefaultTenant \
     --project <PROJECT_ID> --container <SECTION_ID>
   ```

The publisher is already verified up to this permission boundary — it creates the
project and the per-seam test cases with a normal token; only the execution POST
needs the External-App scope.

## Native alternative

Test Manager also imports results automatically when an automated test runs as part
of a **test set via Orchestrator**. `seamproof publish` is the direct path that
needs no test set; the Orchestrator route is the fully-managed one if you wire the
coded automation in [`../sut/automation/`](../sut/automation/) into a test set.
