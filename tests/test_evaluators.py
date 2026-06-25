"""Unit tests for individual assertion kinds."""
from __future__ import annotations

import pytest

from seamproof.errors import ContractError
from seamproof.evaluators import evaluate_assertion

DOC = {
    "handoff": {
        "amount": 4200.0,
        "currency": "USD",
        "vendor_id": "V-1042",
        "confidence": 0.97,
        "exception_flagged": False,
        "line_items": [{"amount": 1200.0}, {"amount": 3000.0}],
    },
    "context": {
        "po": {"currency": "USD"},
        "approved_vendor_master": ["V-1042", "V-2001"],
        "human_review_floor": 9000,
        "min_confidence": 0.90,
    },
    "events": [
        {"id": "e4", "seq": 4, "actor_type": "human", "type": "human.decision", "status": "approved"},
        {"id": "e6", "seq": 6, "actor_type": "robot", "type": "robot.action", "status": "success"},
    ],
    "metrics": {"cost_usd": 0.012, "cycle_seconds": 42},
}


def _run(assertion):
    return evaluate_assertion(DOC, {"id": "t", **assertion})


def test_equals_with_tolerance_passes():
    r = _run({
        "kind": "equals",
        "left": {"ref": "handoff.amount"},
        "right": {"ref": "handoff.line_items[*].amount", "reduce": "sum"},
        "tolerance": 0.005,
    })
    assert r.passed


def test_equals_detects_mismatch():
    r = _run({"kind": "equals", "left": {"ref": "handoff.amount"}, "right": {"const": 5400}, "tolerance": 0.005})
    assert not r.passed
    assert "differs by" in r.detail


def test_in_set_membership():
    assert _run({"kind": "in_set", "value": {"ref": "handoff.vendor_id"}, "set": {"ref": "context.approved_vendor_master"}}).passed
    assert not _run({"kind": "in_set", "value": {"const": "V-9999"}, "set": {"ref": "context.approved_vendor_master"}}).passed


def test_range_exclusive_min():
    assert _run({"kind": "range", "value": {"ref": "handoff.amount"}, "min": 0, "exclusive_min": True}).passed
    assert not _run({"kind": "range", "value": {"const": 0}, "min": 0, "exclusive_min": True}).passed


def test_range_max_against_ref():
    assert _run({"kind": "range", "value": {"ref": "metrics.cost_usd"}, "max": {"const": 0.05}}).passed
    assert not _run({"kind": "range", "value": {"const": 0.11}, "max": {"const": 0.05}}).passed


def test_matches_regex():
    assert _run({"kind": "matches", "value": {"ref": "handoff.currency"}, "pattern": "^[A-Z]{3}$"}).passed


def test_requires_event_present_and_ordered():
    r = _run({
        "kind": "requires_event",
        "when": {"gte": [{"ref": "handoff.amount"}, {"const": 0}]},
        "event": {"actor_type": "human", "type": "human.decision", "where": {"status": "approved"}},
        "before": {"type": "robot.action"},
    })
    assert r.passed


def test_requires_event_missing_fails():
    doc = {**DOC, "events": [{"id": "e6", "seq": 6, "type": "robot.action"}]}
    r = evaluate_assertion(doc, {
        "id": "t",
        "kind": "requires_event",
        "when": {"gte": [{"ref": "handoff.amount"}, {"const": 0}]},
        "event": {"actor_type": "human", "type": "human.decision", "where": {"status": "approved"}},
    })
    assert not r.passed
    assert "contains none" in r.detail


def test_requires_event_not_required_passes():
    # The 'when' is false, so the checkpoint is not applicable for this run.
    r = _run({
        "kind": "requires_event",
        "when": {"eq": [{"ref": "handoff.exception_flagged"}, True]},
        "event": {"actor_type": "human", "type": "human.decision"},
    })
    assert r.passed
    assert "did not require" in r.detail


def test_unknown_kind_raises():
    with pytest.raises(ContractError):
        _run({"kind": "telepathy"})
