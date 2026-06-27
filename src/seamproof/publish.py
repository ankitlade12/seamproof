"""Publish a SeamProof gate result to UiPath Test Manager (REST v2).

The Test Manager v2 result model is test-case-centric and multi-step. These
endpoints and field shapes were verified against a live tenant's Swagger
(``testmanager_/swagger/v2/swagger.json``); every call is tenant-scoped under
``{base}/{org}/{tenant}/testmanager_/``:

  1. ensure a test case exists per seam   ``POST api/v2/{projectId}/testcases``
  2. create a ThirdParty execution        ``POST api/v2/{projectId}/testexecutions``
  3. create a log per seam                ``POST api/v2/{projectId}/testcaselogs``
  4. set each log's result Passed/Failed  ``POST api/v2/{projectId}/testcaselogs/{id}/override-result``
  5. finish the execution                 ``POST api/v2/{projectId}/testexecutions/{id}/finish``

Auth follows UiPath's conventions. With the official ``uipath`` SDK installed and
``uipath auth`` completed, the SDK transport picks up the session automatically;
otherwise a stdlib REST transport uses ``UIPATH_URL`` + ``UIPATH_ACCESS_TOKEN``.
``--dry-run`` builds the full request plan without sending it.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from ._version import __version__
from .errors import SeamProofError
from .evaluators import ContractResult
from .gate import GateResult

# Standard UiPath environment variables (mirrors the uipath SDK's constants).
ENV_BASE_URL = "UIPATH_URL"
ENV_TOKEN = "UIPATH_ACCESS_TOKEN"
ENV_ORG = "UIPATH_ORGANIZATION_ID"
ENV_TENANT = "UIPATH_TENANT_NAME"
ENV_PROJECT = "UIPATH_PROJECT_ID"

SERVICE = "testmanager_"
# Test Manager result enum (verified): None | Passed | Failed | Restricted.
RESULT_PASSED = "Passed"
RESULT_FAILED = "Failed"

# A transport makes one authenticated request and returns the parsed JSON body.
# The body may be a dict, a list (e.g. assign test cases), or None (no body).
Caller = Callable[[str, str, Any], dict[str, Any]]


@dataclass
class PublishConfig:
    base_url: str | None = None
    token: str | None = None
    organization: str | None = None
    tenant: str | None = None
    project_id: str | None = None
    container_id: str | None = None          # section to auto-create test cases in
    testcase_ids: dict[str, str] = field(default_factory=dict)  # seam id -> TM test case id
    test_set: str | None = None
    service: str = SERVICE

    @classmethod
    def from_env(cls, **overrides: Any) -> PublishConfig:
        cfg = cls(
            base_url=os.environ.get(ENV_BASE_URL),
            token=os.environ.get(ENV_TOKEN),
            organization=os.environ.get(ENV_ORG),
            tenant=os.environ.get(ENV_TENANT),
            project_id=os.environ.get(ENV_PROJECT),
        )
        for key, value in overrides.items():
            if value is not None:
                setattr(cfg, key, value)
        return cfg

    def suffix(self, tail: str) -> str:
        """Service-relative path, e.g. ``testmanager_/api/v2/<proj>/testexecutions``."""
        return f"{self.service}/api/v2/{self.project_id}/{tail}"

    @property
    def tenant_base(self) -> str:
        if not self.base_url:
            raise SeamProofError(f"no base URL; set {ENV_BASE_URL} or pass --base-url")
        base = self.base_url.rstrip("/")
        # A UIPATH_URL from `uipath auth` already includes /{org}/{tenant}; only
        # append org/tenant when base_url is a bare host (no path).
        if urlparse(base).path.strip("/"):
            return base
        parts = [base] + [p for p in (self.organization, self.tenant) if p]
        return "/".join(parts)


# --------------------------------------------------------------------------- #
# Result mapping (GateResult -> Test Manager request bodies)
# --------------------------------------------------------------------------- #

def _result_for(cr: ContractResult) -> str:
    return RESULT_PASSED if cr.passed else RESULT_FAILED


def _reason_for(cr: ContractResult) -> str:
    if cr.passed:
        return f"All {len(cr.assertions)} checks passed."
    failed = "; ".join(f"{a.id}: {a.detail}" for a in cr.failures)
    tag = "" if cr.contract.blocking else " (advisory — not blocking the gate)"
    return f"{cr.contract.boundary}{tag} — {failed}"


def _testcase_body(config: PublishConfig, cr: ContractResult) -> dict[str, Any]:
    # automationId must be a GUID, so the seam id goes in foreignReference (a
    # free-form string). containerId is optional; only send it when given.
    body: dict[str, Any] = {
        "name": f"{cr.contract.id} · {cr.contract.name}",
        "description": cr.contract.description or str(cr.contract.boundary),
        "projectId": config.project_id,
        "foreignReference": cr.contract.id,
    }
    if config.container_id:
        body["containerId"] = config.container_id
    return body


def build_payload(
    result: GateResult, config: PublishConfig, testcase_ids: list[str], testset_id: str
) -> dict[str, Any]:
    """The CreateTestExecutionRequest body.

    Verified on the tenant: an execution must reference a test set *and* its test
    cases, and ``source: TestManager`` (``ThirdParty`` 500s for non-automated test
    cases, and ``sourceDetails`` is only accepted with ``ThirdParty``).
    """
    return {
        "projectId": config.project_id,
        "testSetId": testset_id,
        "testCaseIds": testcase_ids,
        "source": "TestManager",
        "name": config.test_set or f"SeamProof — {result.trace.process} ({result.decision.value})",
        "description": (
            f"Gate {result.decision.value} for trace {result.trace.trace_id}: "
            f"{result.total_assertions - result.failed_assertions}/{result.total_assertions} checks passed."
        ),
    }


def _override_body(cr: ContractResult, recommendation: Any = None) -> dict[str, Any]:
    reason = _reason_for(cr)
    if recommendation is not None:
        reason = f"{reason}  ▸ Seam Analyst: {recommendation.recommended_fix}"
    return {"currentResult": _result_for(cr), "reason": reason}


def _finish_body(cr: ContractResult, testcase_id: str) -> dict[str, Any]:
    # Ending the log (not just override-result) is what moves the execution out of
    # "Running" into a terminal status. A failed assertion is a clean Failed, not a
    # runtime error, so hasError stays False.
    return {"testCaseId": testcase_id, "result": _result_for(cr), "runId": 1,
            "hasError": False, "isPostConditionMet": True}


# --------------------------------------------------------------------------- #
# Request plan (used by --dry-run and as the execution order)
# --------------------------------------------------------------------------- #

def plan_requests(result: GateResult, config: PublishConfig) -> list[dict[str, Any]]:
    """Ordered, human-readable plan with placeholders for ids resolved at run time."""
    plan: list[dict[str, Any]] = []
    for cr in result.results:
        if cr.contract.id not in config.testcase_ids:
            plan.append({"purpose": f"create test case {cr.contract.id}", "method": "POST",
                         "path": config.suffix("testcases"), "body": _testcase_body(config, cr)})
    ids = [config.testcase_ids.get(cr.contract.id, f"<{cr.contract.id}>") for cr in result.results]
    plan.append({"purpose": "create test set", "method": "POST",
                 "path": config.suffix("testsets"),
                 "body": {"projectId": config.project_id, "name": config.test_set or "SeamProof seams"}})
    plan.append({"purpose": "assign test cases", "method": "POST",
                 "path": config.suffix("testsets/<set>/assigntestcases"), "body": ids})
    plan.append({"purpose": "create execution", "method": "POST",
                 "path": config.suffix("testexecutions"), "body": build_payload(result, config, ids, "<set>")})
    for cr in result.results:
        tc = config.testcase_ids.get(cr.contract.id, f"<{cr.contract.id}>")
        plan.append({"purpose": f"start log {cr.contract.id}", "method": "POST",
                     "path": config.suffix("testcaselogs/testexecution/<exec>/start"),
                     "body": {"testCaseId": tc, "runId": 1}})
        plan.append({"purpose": f"result {cr.contract.id} = {_result_for(cr)}", "method": "POST",
                     "path": config.suffix("testcaselogs/<log>/override-result"), "body": _override_body(cr)})
        plan.append({"purpose": f"finish log {cr.contract.id} = {_result_for(cr)}", "method": "POST",
                     "path": config.suffix("testcaselogs/testexecution/<exec>/finish"),
                     "body": _finish_body(cr, tc)})
    plan.append({"purpose": "finish execution", "method": "POST",
                 "path": config.suffix("testexecutions/<exec>/finish"), "body": None})
    return plan


# --------------------------------------------------------------------------- #
# Transports
# --------------------------------------------------------------------------- #

def sdk_available() -> bool:
    try:
        import uipath.platform  # noqa: F401
        return True
    except Exception:
        return False


def _sdk_caller(config: PublishConfig) -> Caller:
    from uipath.platform import UiPath

    # An explicit token forces explicit creds; otherwise UiPath() reads the full
    # `uipath auth` session (base url + org/tenant + token), even if --base-url was
    # passed only for the result-URL display.
    client = UiPath(base_url=config.base_url, secret=config.token) if config.token else UiPath()

    def call(method: str, suffix: str, body: Any = None) -> dict[str, Any]:
        response = client.api_client.request(method, suffix, scoped="tenant", json=body)
        text = getattr(response, "text", "") or ""
        return json.loads(text) if text.strip() else {}

    return call


def _rest_caller(config: PublishConfig) -> Caller:
    if not config.token:
        raise SeamProofError(
            f"no access token; run `uipath auth`, set {ENV_TOKEN}, or use --dry-run"
        )

    def call(method: str, suffix: str, body: Any = None) -> dict[str, Any]:
        url = f"{config.tenant_base}/{suffix}"
        request = urllib.request.Request(
            url, data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"SeamProof/{__version__}",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                raw = response.read().decode().strip()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:300]
            hint = ""
            if exc.code in (401, 403):
                hint = (
                    " — token expired or missing a Test Manager scope/role. Posting test "
                    "executions needs a scope `uipath auth` does not grant; use an External "
                    "Application (client credentials) with test-execution scopes."
                )
            raise SeamProofError(f"Test Manager {method} {suffix} -> HTTP {exc.code}: {body}{hint}") from exc
        except urllib.error.URLError as exc:
            raise SeamProofError(f"could not reach Test Manager: {exc.reason}") from exc

    return call


def _default_caller(config: PublishConfig) -> Caller:
    # Prefer the SDK (it carries the uipath-auth session) unless an explicit token
    # forces the dependency-free REST path.
    if sdk_available() and not config.token:
        return _sdk_caller(config)
    return _rest_caller(config)


def _new_id(response: dict[str, Any]) -> str:
    for key in ("id", "Id", "testExecutionId", "testCaseLogId"):
        if response.get(key):
            return str(response[key])
    raise SeamProofError(f"Test Manager response had no id field: {response}")


# --------------------------------------------------------------------------- #
# Publish
# --------------------------------------------------------------------------- #

def publish(
    result: GateResult,
    config: PublishConfig,
    *,
    dry_run: bool = False,
    transport: Caller | None = None,
    recommendations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the execution, log + set each seam's result, and finish it.

    ``recommendations`` optionally maps a seam id to the Seam Analyst's recommendation;
    when present, its fix is appended to that seam's result reason in Test Manager.
    """
    if not config.project_id:
        raise SeamProofError("a Test Manager project id is required (--project or UIPATH_PROJECT_ID)")
    recs = recommendations or {}

    if dry_run:
        return {"dry_run": True, "base": f"{config.tenant_base}/{config.service}",
                "requests": plan_requests(result, config)}

    call = transport or _default_caller(config)
    # 1. ensure a test case exists per seam
    tc_ids = dict(config.testcase_ids)
    for cr in result.results:
        if cr.contract.id not in tc_ids:
            tc_ids[cr.contract.id] = _new_id(call("POST", config.suffix("testcases"), _testcase_body(config, cr)))
    ids = [tc_ids[cr.contract.id] for cr in result.results]

    # 2. a test set holding the seams, 3. assigned via a raw GUID array
    test_set = call("POST", config.suffix("testsets"),
                    {"projectId": config.project_id, "name": config.test_set or "SeamProof seams"})
    set_id = _new_id(test_set)
    call("POST", config.suffix(f"testsets/{set_id}/assigntestcases"), ids)

    # 4. the execution over that set
    execution = call("POST", config.suffix("testexecutions"), build_payload(result, config, ids, set_id))
    exec_id = _new_id(execution)

    # 5. per seam: start a log, record the result + reason, then finish the log
    for cr in result.results:
        tc = tc_ids[cr.contract.id]
        log = call("POST", config.suffix(f"testcaselogs/testexecution/{exec_id}/start"),
                   {"testCaseId": tc, "runId": 1})
        log_id = _new_id(log)
        call("POST", config.suffix(f"testcaselogs/{log_id}/override-result"),
             _override_body(cr, recs.get(cr.contract.id)))
        call("POST", config.suffix(f"testcaselogs/testexecution/{exec_id}/finish"), _finish_body(cr, tc))

    # 6. finish the execution. The per-seam finishes above already move it to a terminal
    # status, so this can report "already started" — that's benign, so tolerate it.
    try:
        call("POST", config.suffix(f"testexecutions/{exec_id}/finish"), None)
    except SeamProofError as exc:
        if "already" not in str(exc).lower():
            raise
    url = None
    if config.base_url:
        url = f"{config.tenant_base}/{config.service}/#/projects/{config.project_id}/executions/{exec_id}"
    return {
        "published": True,
        "project_id": config.project_id,
        "execution_id": exec_id,
        "decision": result.decision.value,
        "url": url,
    }
