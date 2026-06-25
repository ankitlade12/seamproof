"""The small, auditable expression language used inside seam contracts.

Two things live here:

* **References** — ``{ref: "handoff.line_items[*].amount", reduce: sum}`` resolves
  a dotted path (with ``[*]`` wildcards and ``[0]`` indexes) against the
  evaluation document, optionally folding a list with a reducer.
* **Conditions** — ``{gte: [{ref: ...}, {ref: ...}]}`` and the boolean
  combinators ``any`` / ``all`` / ``not`` express the *when* clause of a
  ``requires_event`` assertion.

The language is deliberately data-only: there is no ``eval`` and no arbitrary
code path, so a contract authored by a coding agent can be reviewed like a
policy file rather than trusted like a script.
"""
from __future__ import annotations

import re
from typing import Any

from .errors import ContractError

# Sentinel returned when a path does not resolve. It compares unequal to every
# real value, which is exactly the semantics an assertion wants.
MISSING: Any = type("Missing", (), {"__repr__": lambda self: "<missing>"})()

_SEGMENT = re.compile(r"^([^\[\]]*)((?:\[[^\]]*\])*)$")
_BRACKET = re.compile(r"\[([^\]]*)\]")


def _parse_path(path: str) -> list[tuple[str, Any]]:
    segments: list[tuple[str, Any]] = []
    for part in path.split("."):
        match = _SEGMENT.match(part)
        if not match:
            raise ContractError(f"invalid path segment: {part!r}")
        key, brackets = match.group(1), match.group(2)
        if key:
            segments.append(("key", key))
        for token in _BRACKET.findall(brackets):
            if token == "*":
                segments.append(("wildcard", None))
            else:
                try:
                    segments.append(("index", int(token)))
                except ValueError as exc:
                    raise ContractError(f"invalid list index: [{token}]") from exc
    return segments


def resolve_path(doc: Any, path: str) -> Any:
    """Resolve ``path`` against ``doc``.

    Returns ``MISSING`` for an unresolved scalar path, or a list (with misses
    dropped) when a ``[*]`` wildcard fans the path out across a collection.
    """
    nodes: list[Any] = [doc]
    saw_wildcard = False
    for kind, value in _parse_path(path):
        nxt: list[Any] = []
        for node in nodes:
            if kind == "key":
                nxt.append(node[value] if isinstance(node, dict) and value in node else MISSING)
            elif kind == "index":
                if isinstance(node, list) and -len(node) <= value < len(node):
                    nxt.append(node[value])
                else:
                    nxt.append(MISSING)
            else:  # wildcard
                saw_wildcard = True
                if isinstance(node, list):
                    nxt.extend(node)
        nodes = nxt
    if saw_wildcard:
        return [n for n in nodes if n is not MISSING]
    return nodes[0] if nodes else MISSING


def apply_reduce(values: Any, reducer: str) -> Any:
    if values is MISSING:
        return MISSING
    items = values if isinstance(values, list) else [values]
    numbers = [v for v in items if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if reducer == "count":
        return len(items)
    if reducer == "sum":
        return sum(numbers)
    if reducer == "min":
        return min(numbers) if numbers else MISSING
    if reducer == "max":
        return max(numbers) if numbers else MISSING
    if reducer == "avg":
        return sum(numbers) / len(numbers) if numbers else MISSING
    raise ContractError(f"unknown reducer: {reducer!r}")


def resolve_operand(doc: Any, operand: Any) -> Any:
    """Resolve an operand to a concrete value.

    An operand is either a bare literal, ``{const: <value>}``, or
    ``{ref: "<path>", reduce: "<reducer>"}``.
    """
    if isinstance(operand, dict):
        if "const" in operand:
            return operand["const"]
        if "ref" in operand:
            value = resolve_path(doc, operand["ref"])
            if "reduce" in operand:
                value = apply_reduce(value, operand["reduce"])
            return value
        raise ContractError(f"operand mapping needs 'ref' or 'const': {operand!r}")
    return operand


_COMPARATORS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
}


def evaluate_condition(doc: Any, condition: Any) -> bool:
    """Evaluate a boolean condition tree to ``True`` / ``False``."""
    if not isinstance(condition, dict) or len(condition) != 1:
        raise ContractError(f"condition must be a single-key mapping: {condition!r}")
    op, arg = next(iter(condition.items()))
    if op == "any":
        return any(evaluate_condition(doc, c) for c in arg)
    if op == "all":
        return all(evaluate_condition(doc, c) for c in arg)
    if op == "not":
        return not evaluate_condition(doc, arg)
    if op == "in":
        left = resolve_operand(doc, arg[0])
        right = resolve_operand(doc, arg[1])
        return left is not MISSING and isinstance(right, (list, tuple, str)) and left in right
    if op in _COMPARATORS:
        left = resolve_operand(doc, arg[0])
        right = resolve_operand(doc, arg[1])
        if left is MISSING or right is MISSING:
            # A missing operand can only satisfy an inequality of identity.
            return op == "ne"
        if op in ("gt", "gte", "lt", "lte") and not _orderable(left, right):
            return False
        return _COMPARATORS[op](left, right)
    raise ContractError(f"unknown condition operator: {op!r}")


def _orderable(left: Any, right: Any) -> bool:
    numeric = (int, float)
    if isinstance(left, numeric) and isinstance(right, numeric):
        return True
    return type(left) is type(right) and isinstance(left, (str,))
