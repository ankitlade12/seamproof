"""Tests for the Seam Analyst — the agent that recommends fixes for failed seams."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from seamproof.analyst import Recommendation, analyze, recommend
from seamproof.contracts import load_contracts
from seamproof.gate import evaluate_gate
from seamproof.trace import Trace

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"


def _result(trace_name):
    contracts = load_contracts(CONTRACTS)
    trace = Trace.load(ROOT / "examples" / "traces" / trace_name)
    return evaluate_gate(trace, contracts)


def _by_seam(recs):
    return {r.seam_id: r for r in recs}


def test_clean_run_has_no_recommendations():
    # A GO trace: nothing failed, so the analyst has nothing to recommend.
    assert analyze(_result("golden_happy_path.json"), use_llm=False) == []


def test_one_recommendation_per_failed_seam():
    recs = analyze(_result("seam1_amount_mismatch.json"), use_llm=False)
    assert [r.seam_id for r in recs] == ["seam-1"]
    assert all(isinstance(r, Recommendation) for r in recs)


def test_amount_mismatch_recommends_reconciliation():
    r = _by_seam(analyze(_result("seam1_amount_mismatch.json"), use_llm=False))["seam-1"]
    assert r.source == "heuristic"
    assert r.fragility == "high"
    # the heuristic should name the right remedy for a data-integrity seam
    assert "recompute" in r.recommended_fix.lower() or "reconcil" in r.recommended_fix.lower()
    assert r.root_cause  # non-empty
    assert "fix" in r.reason_line.lower()


def test_skipped_checkpoint_recommends_an_unconditional_gate():
    r = _by_seam(analyze(_result("seam2_skipped_approval.json"), use_llm=False))["seam-2"]
    assert "approval" in r.recommended_fix.lower() or "checkpoint" in r.recommended_fix.lower()
    assert r.fragility == "high"


def test_advisory_failure_is_not_rated_high():
    # seam-3 is advisory (a cost/SLO drift) — it should not be flagged as high fragility.
    recs = _by_seam(analyze(_result("seam3_cost_regression.json"), use_llm=False))
    assert "seam-3" in recs
    assert recs["seam-3"].fragility in ("low", "medium")


def test_recommendation_serialises():
    r = _by_seam(analyze(_result("seam1_amount_mismatch.json"), use_llm=False))["seam-1"]
    d = r.as_dict()
    assert d["seam"] == "seam-1"
    assert {"root_cause", "recommended_fix", "fragility", "source"} <= d.keys()


@pytest.mark.skipif(
    not (os.environ.get("UIPATH_URL") and os.environ.get("UIPATH_ACCESS_TOKEN")),
    reason="needs a live UiPath LLM Gateway (UIPATH_URL + UIPATH_ACCESS_TOKEN)",
)
def test_llm_gateway_analyst_live():
    # With real credentials the analyst runs as an LLM Gateway agent, not the heuristic.
    result = _result("seam1_amount_mismatch.json")
    cr = next(c for c in result.results if not c.passed)
    r = recommend(cr, process=result.trace.process, use_llm=True)
    assert r.source == "llm-gateway"
    assert r.recommended_fix and r.root_cause
    assert r.fragility in ("low", "medium", "high")
