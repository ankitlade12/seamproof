"""Tests for the report renderers."""
from __future__ import annotations

import json
from pathlib import Path
from xml.dom import minidom

import pytest

from seamproof.contracts import load_contracts
from seamproof.gate import evaluate_gate
from seamproof.report import render
from seamproof.trace import Trace

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def seam1_result():
    contracts = load_contracts(ROOT / "contracts")
    trace = Trace.load(ROOT / "examples" / "traces" / "seam1_amount_mismatch.json")
    return evaluate_gate(trace, contracts)


def test_text_report_contains_gate_line(seam1_result):
    text = render(seam1_result, "text", color=False)
    assert "GATE: NO-GO" in text
    assert "seam-1" in text


def test_json_report_is_valid_and_complete(seam1_result):
    payload = json.loads(render(seam1_result, "json"))
    assert payload["decision"] == "NO-GO"
    assert payload["summary"]["blocking_failures"] == ["seam-1"]
    assert len(payload["seams"]) == 3
    # Evidence is carried through for the failing assertion.
    seam1 = next(s for s in payload["seams"] if s["seam"] == "seam-1")
    failing = next(a for a in seam1["assertions"] if not a["passed"])
    assert failing["evidence"]["left"] == 5400.0


def test_junit_report_is_well_formed(seam1_result):
    xml = render(seam1_result, "junit")
    doc = minidom.parseString(xml)
    suites = doc.getElementsByTagName("testsuite")
    assert len(suites) == 3
    failures = doc.getElementsByTagName("failure")
    assert len(failures) >= 1


def test_markdown_report_has_table(seam1_result):
    md = render(seam1_result, "markdown")
    assert "| Seam |" in md
    assert "GATE: NO-GO" in md


def test_unknown_format_raises(seam1_result):
    with pytest.raises(ValueError):
        render(seam1_result, "yaml")
