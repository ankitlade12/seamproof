"""Evaluate seam contracts against a run trace.

Each assertion ``kind`` is a small, named property check. Adding a new kind means
registering one function below — contracts never grow the ability to run code,
which keeps the trust boundary at the data layer.

The evaluation document handed to every assertion is::

    {
        "handoff":  <attributes of the event that crosses the boundary>,
        "context":  <static run context: PO, vendor master, ceilings, SLOs>,
        "events":   [<flat view of every trace event>],
        "metrics":  <attributes of the run.metrics event>,
    }
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .contracts import Contract
from .errors import ContractError
from .expr import MISSING, evaluate_condition, resolve_operand
from .trace import Trace


@dataclass
class AssertionResult:
    id: str
    kind: str
    passed: bool
    description: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContractResult:
    contract: Contract
    assertions: list[AssertionResult]

    @property
    def passed(self) -> bool:
        return all(a.passed for a in self.assertions)

    @property
    def failures(self) -> list[AssertionResult]:
        return [a for a in self.assertions if not a.passed]


# --------------------------------------------------------------------------- #
# Evaluation-document construction
# --------------------------------------------------------------------------- #

def build_document(trace: Trace, contract: Contract) -> dict[str, Any]:
    handoff: dict[str, Any] = {}
    locator = contract.handoff.get("source")
    if isinstance(locator, dict):
        event = trace.first(**locator)
        if event is not None:
            handoff = dict(event.attributes)
    return {
        "handoff": handoff,
        "context": trace.context,
        "events": trace.event_docs(),
        "metrics": trace.metrics(),
    }


# --------------------------------------------------------------------------- #
# Assertion kinds
# --------------------------------------------------------------------------- #

def _fmt(value: Any) -> str:
    if value is MISSING:
        return "<missing>"
    if isinstance(value, float):
        return f"{value:g}"
    return repr(value)


def _numbers_close(a: Any, b: Any, tolerance: float) -> bool:
    return (
        isinstance(a, (int, float))
        and isinstance(b, (int, float))
        and abs(a - b) <= tolerance
    )


def _assert_equals(doc: dict[str, Any], a: dict[str, Any]) -> tuple[bool, str, dict]:
    left = resolve_operand(doc, a["left"])
    right = resolve_operand(doc, a["right"])
    tolerance = a.get("tolerance")
    if tolerance is not None:
        passed = _numbers_close(left, right, float(tolerance))
        detail = (
            f"expected {_fmt(left)} == {_fmt(right)} (±{tolerance}); "
            + ("matched" if passed else f"differs by {_fmt(abs(left - right))}"
               if _numbers_close(left, right, float("inf")) else "non-numeric operand")
        )
    else:
        passed = left is not MISSING and right is not MISSING and left == right
        detail = f"expected {_fmt(left)} == {_fmt(right)}; " + ("matched" if passed else "differs")
    return passed, detail, {"left": _safe(left), "right": _safe(right), "tolerance": tolerance}


def _assert_not_equals(doc: dict[str, Any], a: dict[str, Any]) -> tuple[bool, str, dict]:
    left = resolve_operand(doc, a["left"])
    right = resolve_operand(doc, a["right"])
    passed = left != right
    return passed, f"expected {_fmt(left)} != {_fmt(right)}", {"left": _safe(left), "right": _safe(right)}


def _assert_in_set(doc: dict[str, Any], a: dict[str, Any]) -> tuple[bool, str, dict]:
    value = resolve_operand(doc, a["value"])
    allowed = resolve_operand(doc, a["set"])
    passed = isinstance(allowed, list) and value in allowed
    detail = f"expected {_fmt(value)} to be one of {len(allowed) if isinstance(allowed, list) else 0} allowed values"
    return passed, detail, {"value": _safe(value), "allowed": _safe(allowed)}


def _assert_matches(doc: dict[str, Any], a: dict[str, Any]) -> tuple[bool, str, dict]:
    value = resolve_operand(doc, a["value"])
    pattern = a["pattern"]
    passed = isinstance(value, str) and re.search(pattern, value) is not None
    return passed, f"expected {_fmt(value)} to match /{pattern}/", {"value": _safe(value), "pattern": pattern}


def _assert_range(doc: dict[str, Any], a: dict[str, Any]) -> tuple[bool, str, dict]:
    value = resolve_operand(doc, a["value"])
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False, f"expected a number, got {_fmt(value)}", {"value": _safe(value)}
    parts: list[str] = []
    passed = True
    evidence: dict[str, Any] = {"value": value}
    if "min" in a:
        lo = resolve_operand(doc, a["min"])
        evidence["min"] = _safe(lo)
        ok = value > lo if a.get("exclusive_min") else value >= lo
        passed = passed and ok
        parts.append(f"{'>' if a.get('exclusive_min') else '>='} {_fmt(lo)}")
    if "max" in a:
        hi = resolve_operand(doc, a["max"])
        evidence["max"] = _safe(hi)
        ok = value < hi if a.get("exclusive_max") else value <= hi
        passed = passed and ok
        parts.append(f"{'<' if a.get('exclusive_max') else '<='} {_fmt(hi)}")
    return passed, f"expected {_fmt(value)} {' and '.join(parts) or 'within range'}", evidence


def _find_events(events: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    where = spec.get("where", {})
    selectors = {k: v for k, v in spec.items() if k != "where"}
    found = []
    for event in events:
        if all(event.get(k) == v for k, v in selectors.items()) and all(
            event.get(k) == v for k, v in where.items()
        ):
            found.append(event)
    return found


def _describe_event(spec: dict[str, Any]) -> str:
    parts = [f"{k}={v}" for k, v in spec.items() if k != "where"]
    parts += [f"{k}={v}" for k, v in spec.get("where", {}).items()]
    return " ".join(parts) or "event"


def _assert_requires_event(doc: dict[str, Any], a: dict[str, Any]) -> tuple[bool, str, dict]:
    when = a.get("when")
    required = evaluate_condition(doc, when) if when is not None else True
    spec = a["event"]
    described = _describe_event(spec)
    matched = _find_events(doc["events"], spec)
    evidence = {
        "required": required,
        "matched_event_ids": [e["id"] for e in matched],
    }
    if not required:
        return True, "policy did not require this checkpoint for this run", evidence

    if not matched:
        return False, f"policy required an event [{described}] but the trace contains none", evidence

    before = a.get("before")
    if before:
        boundary = _find_events(doc["events"], before)
        if boundary:
            first_boundary_seq = min(e["seq"] for e in boundary)
            in_order = any(e["seq"] < first_boundary_seq for e in matched)
            evidence["before_event_ids"] = [e["id"] for e in boundary]
            if not in_order:
                return (
                    False,
                    f"required event [{described}] occurred, but not before [{_describe_event(before)}]",
                    evidence,
                )
    return True, f"required checkpoint present [{described}]", evidence


_KINDS: dict[str, Callable[[dict, dict], tuple[bool, str, dict]]] = {
    "equals": _assert_equals,
    "not_equals": _assert_not_equals,
    "in_set": _assert_in_set,
    "matches": _assert_matches,
    "range": _assert_range,
    "requires_event": _assert_requires_event,
}


def _safe(value: Any) -> Any:
    """Make a resolved value JSON-serialisable for the evidence payload."""
    if value is MISSING:
        return None
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _safe(v) for k, v in value.items()}
    return str(value)


def evaluate_assertion(doc: dict[str, Any], assertion: dict[str, Any]) -> AssertionResult:
    kind = assertion["kind"]
    handler = _KINDS.get(kind)
    if handler is None:
        raise ContractError(f"unknown assertion kind: {kind!r}")
    passed, detail, evidence = handler(doc, assertion)
    return AssertionResult(
        id=assertion["id"],
        kind=kind,
        passed=passed,
        description=assertion.get("description", ""),
        detail=detail,
        evidence=evidence,
    )


def evaluate_contract(trace: Trace, contract: Contract) -> ContractResult:
    doc = build_document(trace, contract)
    results = [evaluate_assertion(doc, assertion) for assertion in contract.assertions]
    return ContractResult(contract=contract, assertions=results)
