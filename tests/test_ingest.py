"""Tests for the OpenTelemetry (Maestro OTLP) trace ingester."""
from __future__ import annotations

from pathlib import Path

import pytest

from seamproof.contracts import load_contracts
from seamproof.errors import TraceError
from seamproof.gate import evaluate_gate
from seamproof.ingest import _otel_value, otel_to_trace, trace_from_otel

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "examples" / "otel" / "maestro_seam1_export.json"


def test_otel_value_decodes_every_type():
    assert _otel_value({"stringValue": "x"}) == "x"
    assert _otel_value({"intValue": "10000"}) == 10000
    assert _otel_value({"doubleValue": 0.05}) == 0.05
    assert _otel_value({"boolValue": False}) is False
    assert _otel_value({"arrayValue": {"values": [{"stringValue": "a"}, {"stringValue": "b"}]}}) == ["a", "b"]
    nested = _otel_value({"kvlistValue": {"values": [{"key": "k", "value": {"intValue": "2"}}]}})
    assert nested == {"k": 2}


def test_ingest_fixture_shape():
    trace = trace_from_otel(FIXTURE)
    assert trace.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert trace.process == "invoice-exception-handling"
    # run.context is lifted into context, not kept as an event (6 spans -> 5 events).
    assert len(trace.events) == 5
    assert trace.events[0].type == "agent.output"
    assert "run.context" not in {e.type for e in trace.events}


def test_ingest_decodes_nested_context():
    trace = trace_from_otel(FIXTURE)
    assert trace.context["po"]["currency"] == "USD"
    assert trace.context["approved_vendor_master"] == ["V-1042", "V-1043", "V-2001", "V-3300"]
    assert trace.context["sla"]["max_cost_usd"] == 0.05
    assert trace.context["auto_post_ceiling"] == 10000


def test_ingest_preserves_line_items_for_seam1():
    trace = trace_from_otel(FIXTURE)
    robot_input = next(e for e in trace.events if e.type == "robot.input")
    amounts = [li["amount"] for li in robot_input.attributes["line_items"]]
    assert amounts == [1200.0, 3000.0]
    assert robot_input.attributes["amount"] == 5400.0


def test_ingested_trace_gates_no_go():
    trace = trace_from_otel(FIXTURE)
    result = evaluate_gate(trace, load_contracts(ROOT / "contracts"))
    assert result.decision.value == "NO-GO"
    assert [cr.contract.id for cr in result.blocking_failures] == ["seam-1"]


def test_external_context_overrides_span_context():
    import json
    otel = json.loads(FIXTURE.read_text())
    trace = otel_to_trace(otel, context={"min_confidence": 0.99, "extra": True})
    assert trace.context["min_confidence"] == 0.99   # external wins over the run.context span
    assert trace.context["extra"] is True
    assert trace.context["auto_post_ceiling"] == 10000  # span-provided values survive


def test_empty_otel_raises():
    with pytest.raises(TraceError):
        otel_to_trace({"resourceSpans": []})
