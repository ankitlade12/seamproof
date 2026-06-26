"""Tests for the UiPath Test Manager publisher."""
from __future__ import annotations

from pathlib import Path

import pytest

from seamproof.contracts import load_contracts
from seamproof.errors import SeamProofError
from seamproof.gate import evaluate_gate
from seamproof.publish import (
    PublishConfig,
    build_payload,
    publish,
    rest_transport,
)
from seamproof.trace import Trace

ROOT = Path(__file__).resolve().parent.parent


def _result(trace_name):
    contracts = load_contracts(ROOT / "contracts")
    trace = Trace.load(ROOT / "examples" / "traces" / trace_name)
    return evaluate_gate(trace, contracts)


def test_payload_marks_blocking_failure():
    result = _result("seam1_amount_mismatch.json")
    payload = build_payload(result, PublishConfig(project_id="P1"))
    assert payload["status"] == "Failed"
    assert payload["projectId"] == "P1"
    assert len(payload["testCases"]) == 3
    seam1 = next(tc for tc in payload["testCases"] if tc["externalId"] == "seam-1")
    assert seam1["status"] == "Failed"
    assert any(step["status"] == "Failed" for step in seam1["steps"])


def test_payload_advisory_failure_does_not_fail_case():
    result = _result("seam3_cost_regression.json")
    payload = build_payload(result, PublishConfig())
    assert payload["status"] == "Passed"  # gate is GO
    seam3 = next(tc for tc in payload["testCases"] if tc["externalId"] == "seam-3")
    assert seam3["status"] == "Passed"  # advisory: reported but not failed
    assert any(step["status"] == "Failed" for step in seam3["steps"])  # ...with failing steps recorded


def test_dry_run_builds_payload_without_sending():
    result = _result("seam1_amount_mismatch.json")
    config = PublishConfig(base_url="https://cloud.uipath.com", project_id="P1")
    out = publish(result, config, dry_run=True)
    assert out["dry_run"] is True
    assert out["payload"]["status"] == "Failed"
    assert "P1" in out["endpoint"]


def test_publish_uses_injected_transport():
    result = _result("golden_happy_path.json")
    captured = {}

    def fake_transport(config, payload):
        captured["url"] = config.full_url
        captured["payload"] = payload
        return {"transport": "fake", "status_code": 201}

    config = PublishConfig(base_url="https://cloud.uipath.com", token="t", project_id="P9")
    out = publish(result, config, transport=fake_transport)
    assert out["status_code"] == 201
    assert captured["payload"]["status"] == "Passed"
    assert "P9" in captured["url"]


def test_config_from_env_and_overrides(monkeypatch):
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "secret-token")
    monkeypatch.setenv("UIPATH_PROJECT_ID", "P-env")
    config = PublishConfig.from_env()
    assert config.base_url == "https://cloud.uipath.com"
    assert config.token == "secret-token"
    assert config.project_id == "P-env"
    overridden = PublishConfig.from_env(project_id="P-arg")
    assert overridden.project_id == "P-arg"


def test_full_url_scopes_org_and_tenant():
    config = PublishConfig(
        base_url="https://cloud.uipath.com/",
        organization="acme",
        tenant="default",
        project_id="P1",
        endpoint="testmanager_/api/v1/projects/{project_id}/x",
    )
    assert config.full_url == "https://cloud.uipath.com/acme/default/testmanager_/api/v1/projects/P1/x"


def test_rest_transport_requires_token():
    config = PublishConfig(base_url="https://cloud.uipath.com", token=None, project_id="P1")
    with pytest.raises(SeamProofError):
        rest_transport(config, {"any": "payload"})
