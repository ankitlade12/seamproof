"""End-to-end test of the UiPath coded-automation SUT.

Loads the real automation entrypoint (``sut/automation/main.py``), runs each case
offline, and gates the OTLP it emits through SeamProof. This proves the full
SUT -> OTEL -> gate pipeline without a tenant (the automation's UiPath imports
degrade to no-ops when the SDK is absent).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from seamproof.contracts import load_contracts
from seamproof.gate import evaluate_gate
from seamproof.ingest import otel_to_trace

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "sut" / "automation" / "main.py"


def _load_automation():
    name = "sut_automation_main"
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve cls.__module__ (the same
    # way `uipath run` and `python main.py` load it as a top-level module).
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


automation = _load_automation()
CONTRACTS = load_contracts(ROOT / "contracts")


@pytest.mark.parametrize(
    "case, decision, blocking",
    [
        ("golden", "GO", []),
        ("high_value", "GO", []),
        ("seam1_corruption", "NO-GO", ["seam-1"]),
        ("seam2_near_ceiling", "NO-GO", ["seam-2"]),
    ],
)
def test_sut_case_gates_as_expected(case, decision, blocking):
    output = automation.process(automation.ProcessInput(case=case))
    trace = otel_to_trace(output.otlp)
    result = evaluate_gate(trace, CONTRACTS)
    assert result.decision.value == decision, case
    assert sorted(cr.contract.id for cr in result.blocking_failures) == sorted(blocking), case


def test_sut_emits_well_formed_otlp():
    output = automation.process(automation.ProcessInput(case="golden"))
    spans = output.otlp["resourceSpans"][0]["scopeSpans"][0]["spans"]
    names = {s["name"] for s in spans}
    # run.context is lifted into context by the ingester; the rest become events.
    assert {"run.context", "agent.output", "routing.decision", "robot.input", "robot.action", "run.metrics"} <= names


def test_seam2_routing_bug_skips_human():
    """The ceiling-only gateway auto-posts the $9,950 case (no human.decision span)."""
    output = automation.process(automation.ProcessInput(case="seam2_near_ceiling"))
    assert output.route == "auto-post"
    names = [s["name"] for s in output.otlp["resourceSpans"][0]["scopeSpans"][0]["spans"]]
    assert "human.decision" not in names


def test_high_value_routes_through_human():
    """The high-value case routes to a human and records an approved decision."""
    output = automation.process(automation.ProcessInput(case="high_value"))
    assert output.route == "human-review"
    names = [s["name"] for s in output.otlp["resourceSpans"][0]["scopeSpans"][0]["spans"]]
    assert "human.decision" in names


def test_extract_entrypoint_returns_recon():
    """The recon-only entrypoint (used by `uipath eval`) returns the structured fields."""
    recon = automation.extract(automation.ExtractInput(case="golden"))
    assert recon["amount"] == 4200.0
    assert sum(item["amount"] for item in recon["line_items"]) == 4200.0
    assert recon["exception_flagged"] is False
