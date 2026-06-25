"""Data-driven gate tests, driven by the scenario suite.

This is the regression backbone: every scenario in
``scenarios/invoice-exception.suite.yaml`` is run through the real engine and
its declared gate outcome is asserted. Golden traces must pass; each injected
failure must trip exactly its seam.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from seamproof.contracts import load_contracts
from seamproof.gate import evaluate_gate
from seamproof.trace import Trace

ROOT = Path(__file__).resolve().parent.parent
SUITE = yaml.safe_load((ROOT / "scenarios" / "invoice-exception.suite.yaml").read_text())
SCENARIOS = SUITE["scenarios"]


@pytest.fixture(scope="module")
def contracts():
    return load_contracts(ROOT / SUITE["contracts"])


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario_outcome(scenario, contracts):
    expect = scenario["expect"]
    trace = Trace.load(ROOT / scenario["trace"])
    result = evaluate_gate(trace, contracts)

    assert result.decision.value == expect["decision"], scenario["id"]

    if "blocking_failures" in expect:
        got = sorted(cr.contract.id for cr in result.blocking_failures)
        assert got == sorted(expect["blocking_failures"]), scenario["id"]

    if "advisory_failures" in expect:
        got = sorted(cr.contract.id for cr in result.advisory_failures)
        assert got == sorted(expect["advisory_failures"]), scenario["id"]

    if "failed_assertions" in expect:
        got = {a.id for cr in result.results for a in cr.failures}
        for expected_id in expect["failed_assertions"]:
            assert expected_id in got, f"{scenario['id']}: expected {expected_id} to fail"


def test_every_trace_is_covered():
    """Guard against an untested sample trace sneaking into the repo."""
    referenced = {Path(s["trace"]).name for s in SCENARIOS}
    on_disk = {p.name for p in (ROOT / "examples" / "traces").glob("*.json")}
    assert on_disk == referenced, f"untested traces: {on_disk - referenced}"
