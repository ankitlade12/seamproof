"""Tests for the UiPath Test Manager (v2) publisher."""
from __future__ import annotations

from pathlib import Path

import pytest

from seamproof.contracts import load_contracts
from seamproof.errors import SeamProofError
from seamproof.gate import evaluate_gate
from seamproof.publish import (
    PublishConfig,
    build_payload,
    plan_requests,
    publish,
)
from seamproof.trace import Trace

ROOT = Path(__file__).resolve().parent.parent
IDS = {"seam-1": "t1", "seam-2": "t2", "seam-3": "t3"}


def _result(trace_name):
    contracts = load_contracts(ROOT / "contracts")
    trace = Trace.load(ROOT / "examples" / "traces" / trace_name)
    return evaluate_gate(trace, contracts)


def test_execution_payload_uses_testmanager_source():
    result = _result("seam1_amount_mismatch.json")
    body = build_payload(result, PublishConfig(project_id="P1"), ["t1", "t2", "t3"], "set-1")
    assert body["source"] == "TestManager"        # ThirdParty 500s for non-automated cases
    assert body["testSetId"] == "set-1"
    assert body["testCaseIds"] == ["t1", "t2", "t3"]
    assert "NO-GO" in body["name"]


def test_plan_maps_results_to_passed_failed():
    result = _result("seam1_amount_mismatch.json")  # seam-1 fails, seam-2/3 pass
    plan = plan_requests(result, PublishConfig(project_id="P1", testcase_ids=IDS))
    overrides = {r["purpose"] for r in plan if "override-result" in r["path"]}
    assert "result seam-1 = Failed" in overrides
    assert "result seam-2 = Passed" in overrides
    assert "result seam-3 = Passed" in overrides


def test_suffix_and_tenant_base():
    config = PublishConfig(
        base_url="https://staging.uipath.com/", organization="acme",
        tenant="DefaultTenant", project_id="P1",
    )
    assert config.suffix("testexecutions") == "testmanager_/api/v2/P1/testexecutions"
    assert config.tenant_base == "https://staging.uipath.com/acme/DefaultTenant"


def test_dry_run_builds_full_plan_without_sending():
    result = _result("seam1_amount_mismatch.json")
    config = PublishConfig(base_url="https://staging.uipath.com", organization="o",
                           tenant="t", project_id="P1", testcase_ids=IDS)
    out = publish(result, config, dry_run=True)
    assert out["dry_run"] is True
    purposes = [r["purpose"] for r in out["requests"]]
    assert "create execution" in purposes
    assert "finish execution" in purposes


def test_publish_runs_full_flow_with_existing_testcases():
    result = _result("seam1_amount_mismatch.json")  # 3 seams
    calls = []
    counter = {"n": 0}

    def fake(method, suffix, body):
        calls.append((method, suffix))
        counter["n"] += 1
        return {"id": f"id-{counter['n']}"}

    config = PublishConfig(base_url="https://staging.uipath.com", organization="o",
                           tenant="t", project_id="P1", testcase_ids=IDS)
    out = publish(result, config, transport=fake)
    assert out["published"] is True
    # testset + assign + execution + (3 start-logs + 3 results) + finish = 10 (cases pre-exist)
    assert len(calls) == 10
    assert all(m == "POST" for m, _ in calls)
    assert any("api/v2/P1/testexecutions" in s for _, s in calls)
    assert any("testsets" in s for _, s in calls)


def test_publish_auto_creates_testcases_with_container():
    result = _result("seam1_amount_mismatch.json")
    calls = []
    counter = {"n": 0}

    def fake(method, suffix, body):
        calls.append(suffix)
        counter["n"] += 1
        return {"id": f"id-{counter['n']}"}

    config = PublishConfig(base_url="https://staging.uipath.com", organization="o",
                           tenant="t", project_id="P1", container_id="C1")
    publish(result, config, transport=fake)
    # 3 test cases + testset + assign + execution + 6 (start/result) + finish = 13 calls
    assert len(calls) == 13
    assert sum(s.endswith("/testcases") for s in calls) == 3


def test_publish_requires_project():
    result = _result("golden_happy_path.json")
    with pytest.raises(SeamProofError):
        publish(result, PublishConfig(base_url="https://x"), transport=lambda *a: {"id": "x"})


def test_publish_auto_creates_without_container():
    result = _result("golden_happy_path.json")
    calls = []

    def fake(method, suffix, body):
        calls.append(suffix)
        return {"id": f"id-{len(calls)}"}

    publish(result, PublishConfig(base_url="https://x", project_id="P1"), transport=fake)
    assert sum(s.endswith("/testcases") for s in calls) == 3  # auto-created, no container required


def test_tenant_base_respects_full_url():
    # A UIPATH_URL from `uipath auth` already includes /{org}/{tenant}: don't re-append.
    config = PublishConfig(
        base_url="https://staging.uipath.com/hackathon26_1024/DefaultTenant",
        organization="cc12aa98-guid", tenant="ignored",
    )
    assert config.tenant_base == "https://staging.uipath.com/hackathon26_1024/DefaultTenant"


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("UIPATH_URL", "https://staging.uipath.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("UIPATH_PROJECT_ID", "P-env")
    config = PublishConfig.from_env()
    assert config.base_url == "https://staging.uipath.com"
    assert config.token == "tok"
    assert config.project_id == "P-env"
