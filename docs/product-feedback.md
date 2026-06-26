# UiPath product feedback

Specific feedback from building SeamProof on the platform — for the Best Product
Feedback form. All of it comes from actually shipping against the hackathon tenant,
not a survey.

## What worked really well

- **`uipath` Python SDK + CLI.** `uipath new` → `uipath init` → `uipath run` is a
  clean coded-automation loop. `init` statically analyzing the code into an
  entry-point call-graph (`entry-points.json`) is a genuinely nice touch.
- **`@traced` decorator.** Instrumenting steps and getting a trace tree for free is
  exactly the right ergonomics for observability.
- **`uipath eval`.** Native agent evaluation with typed evaluators
  (JSON-similarity, LLM-judge) is excellent for Track 3 — it made "test the agent in
  isolation" a one-command story.
- **UiPath LLM Gateway via `uipath-langchain` (`UiPathChat`).** Dropping the UiPath
  Gateway in as a LangChain `BaseChatModel` made the cross-platform story trivial —
  an external LangChain agent runs through the AI Trust Layer with no glue.

## Friction and gaps (the useful part)

1. **Test Manager has no documented "post external results" API.** The v1 swagger is
   test-case/connector CRUD; results live in **v2** (`/api/v2/{projectId}/...`),
   discoverable only via the tenant's Swagger. A documented "import automated
   results" REST recipe would save hours.
2. **Test-execution scope isn't granted by `uipath auth`.** With an interactive
   token I can create projects and test **cases** (`TM.TestCases`) but `POST
   .../testexecutions` returns **403** — there's no test-execution scope in the
   default scope set. The path (External Application with execution scopes) isn't
   obvious; surfacing it in the Test Manager API docs would help.
3. **`testcases.automationId` requires a GUID** but the validation error
   (`Error converting value "seam-1" to System.Nullable[Guid]`) doesn't say what it
   wants. A clearer message ("automationId must be a UiPath automation GUID; use
   foreignReference for external ids") would be friendlier.
4. **Test Manager API returns the SPA (HTML) without `Accept: application/json`.**
   A missing Accept header silently yields the web app instead of a 406/JSON error —
   easy to mis-debug.
5. **`UIPATH_URL` from `uipath auth` already includes `/{org}/{tenant}`, but
   `UIPATH_ORGANIZATION_ID` is also set.** Tools that compose `base/{org}/{tenant}`
   double-append and 404. A note (or a canonical "service base" helper in the SDK)
   would prevent it.
6. **`UiPath()` in a plain script doesn't auto-load the `.env` `uipath auth` wrote.**
   `uipath run` loads it, but a standalone `UiPath()` raised `BaseUrlMissingError`
   until the `.env` was sourced. Auto-loading (or a clear hint) would be smoother.
7. **LLM Gateway returns model-formatted numbers** (`"5,400.00"`) through structured
   output — expected, but a note that you must coerce types yourself is worth adding
   to the `uipath-langchain` docs.

## One-line ask

Publish the **Test Manager v2 "import automated results" flow** (endpoints + the
required scope/External-App setup) as a first-class doc. It's the last mile for any
CI/CD or third-party test-results integration, and today it's reverse-engineered
from Swagger.
