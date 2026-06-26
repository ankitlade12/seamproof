"""Publish a SeamProof gate result to UiPath Test Manager.

This is the output bridge: it maps a :class:`GateResult` onto the Test Manager
result model (an execution composed of per-test-case logs) and posts it through
the **UiPath Automation Cloud** REST API, authenticated with UiPath's standard
credentials.

Two transports, same payload:

* **SDK transport** — uses the official ``uipath`` package
  (``from uipath.platform import UiPath``) so auth, base-URL, and org/tenant
  scoping are handled by UiPath itself. Enabled when ``uipath`` is installed
  (``pip install "seamproof[uipath]"``).
* **REST transport** — a stdlib ``urllib`` fallback using ``UIPATH_URL`` +
  ``UIPATH_ACCESS_TOKEN`` Bearer auth, so the core package needs no extra
  dependency.

``--dry-run`` builds and returns the exact payload without sending it, so the
mapping is fully testable offline and ready to point at a tenant the moment
credentials exist.

The REST resource path follows the Test Manager API
(https://docs.uipath.com/test-manager/automation-cloud/latest/user-guide/test-manager-api-integration);
confirm the exact path against your tenant's API version, or override it with
``--endpoint``.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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

DEFAULT_ENDPOINT = "testmanager_/api/v1/projects/{project_id}/automated-executions"

Transport = Callable[["PublishConfig", dict[str, Any]], dict[str, Any]]


@dataclass
class PublishConfig:
    base_url: str | None = None
    token: str | None = None
    organization: str | None = None
    tenant: str | None = None
    project_id: str | None = None
    endpoint: str = DEFAULT_ENDPOINT
    test_set: str | None = None

    @classmethod
    def from_env(cls, **overrides: Any) -> PublishConfig:
        env = cls(
            base_url=os.environ.get(ENV_BASE_URL),
            token=os.environ.get(ENV_TOKEN),
            organization=os.environ.get(ENV_ORG),
            tenant=os.environ.get(ENV_TENANT),
            project_id=os.environ.get(ENV_PROJECT),
        )
        for key, value in overrides.items():
            if value is not None:
                setattr(env, key, value)
        return env

    @property
    def relative_path(self) -> str:
        return self.endpoint.format(project_id=self.project_id or "")

    @property
    def full_url(self) -> str:
        if not self.base_url:
            raise SeamProofError(f"no base URL; set {ENV_BASE_URL} or pass --base-url")
        parts = [self.base_url.rstrip("/")]
        parts += [p for p in (self.organization, self.tenant) if p]
        parts.append(self.relative_path.lstrip("/"))
        return "/".join(parts)


# --------------------------------------------------------------------------- #
# Payload mapping (GateResult -> Test Manager result model)
# --------------------------------------------------------------------------- #

def _test_case(cr: ContractResult) -> dict[str, Any]:
    blocking_failure = cr.contract.blocking and not cr.passed
    return {
        "name": f"{cr.contract.id} · {cr.contract.name}",
        "externalId": cr.contract.id,
        "status": "Failed" if blocking_failure else "Passed",
        "severity": cr.contract.severity,
        "boundary": str(cr.contract.boundary),
        "steps": [
            {
                "name": a.id,
                "status": "Passed" if a.passed else "Failed",
                "log": a.detail,
            }
            for a in cr.assertions
        ],
    }


def build_payload(result: GateResult, config: PublishConfig) -> dict[str, Any]:
    failed = not result.decision.is_go
    return {
        "name": config.test_set or f"SeamProof — {result.trace.process}",
        "externalReference": result.trace.trace_id,
        "projectId": config.project_id,
        "status": "Failed" if failed else "Passed",
        "tool": {"name": "SeamProof", "version": __version__},
        "summary": {
            "decision": result.decision.value,
            "totalAssertions": result.total_assertions,
            "failedAssertions": result.failed_assertions,
            "blockingFailures": [cr.contract.id for cr in result.blocking_failures],
            "advisoryFailures": [cr.contract.id for cr in result.advisory_failures],
        },
        "testCases": [_test_case(cr) for cr in result.results],
    }


# --------------------------------------------------------------------------- #
# Transports
# --------------------------------------------------------------------------- #

def sdk_available() -> bool:
    try:
        import uipath.platform  # noqa: F401
        return True
    except Exception:
        return False


def sdk_transport(config: PublishConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Post via the official uipath SDK (handles auth + org/tenant scoping)."""
    try:
        from uipath.platform import UiPath
    except Exception as exc:  # pragma: no cover - exercised only with the extra installed
        raise SeamProofError(
            "the uipath SDK is not installed; run `pip install \"seamproof[uipath]\"` "
            "or use the REST transport / --dry-run"
        ) from exc
    client = UiPath(base_url=config.base_url, secret=config.token)
    response = client.api_client.request(
        "POST", config.relative_path, scoped="tenant", json=payload
    )
    return {"transport": "sdk", "status_code": response.status_code, "body": response.text}


def rest_transport(config: PublishConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Post via stdlib urllib using UIPATH_URL + UIPATH_ACCESS_TOKEN Bearer auth."""
    if not config.token:
        raise SeamProofError(f"no access token; set {ENV_TOKEN} or pass --token, or use --dry-run")
    request = urllib.request.Request(
        config.full_url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
            "User-Agent": f"SeamProof/{__version__}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (https URL)
            return {"transport": "rest", "status_code": response.status, "body": response.read().decode()}
    except urllib.error.HTTPError as exc:
        raise SeamProofError(
            f"Test Manager returned HTTP {exc.code}: {exc.read().decode()[:300]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise SeamProofError(f"could not reach Test Manager: {exc.reason}") from exc


def publish(
    result: GateResult,
    config: PublishConfig,
    *,
    dry_run: bool = False,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Build the payload and (unless ``dry_run``) send it to Test Manager."""
    payload = build_payload(result, config)
    if dry_run:
        endpoint = config.full_url if config.base_url else config.relative_path
        return {"dry_run": True, "endpoint": endpoint, "payload": payload}
    if transport is None:
        transport = sdk_transport if sdk_available() else rest_transport
    return transport(config, payload)
