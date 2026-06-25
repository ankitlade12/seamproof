"""Unit tests for the contract expression language."""
from __future__ import annotations

import pytest

from seamproof.errors import ContractError
from seamproof.expr import (
    MISSING,
    apply_reduce,
    evaluate_condition,
    resolve_operand,
    resolve_path,
)

DOC = {
    "handoff": {
        "amount": 4200.0,
        "currency": "USD",
        "line_items": [{"amount": 1200.0}, {"amount": 3000.0}],
    },
    "context": {"po": {"currency": "USD"}, "vendors": ["V-1", "V-2"], "floor": 9000},
}


def test_resolve_simple_path():
    assert resolve_path(DOC, "handoff.amount") == 4200.0
    assert resolve_path(DOC, "context.po.currency") == "USD"


def test_resolve_missing_path_returns_sentinel():
    assert resolve_path(DOC, "handoff.nope") is MISSING
    assert resolve_path(DOC, "handoff.amount.deeper") is MISSING


def test_resolve_index_and_wildcard():
    assert resolve_path(DOC, "handoff.line_items[0].amount") == 1200.0
    assert resolve_path(DOC, "handoff.line_items[*].amount") == [1200.0, 3000.0]


def test_reduce_sum_and_count():
    values = resolve_path(DOC, "handoff.line_items[*].amount")
    assert apply_reduce(values, "sum") == 4200.0
    assert apply_reduce(values, "count") == 2


def test_reduce_unknown_raises():
    with pytest.raises(ContractError):
        apply_reduce([1, 2], "median")


def test_resolve_operand_const_ref_literal():
    assert resolve_operand(DOC, {"const": 10}) == 10
    assert resolve_operand(DOC, {"ref": "handoff.currency"}) == "USD"
    assert resolve_operand(DOC, {"ref": "handoff.line_items[*].amount", "reduce": "sum"}) == 4200.0
    assert resolve_operand(DOC, 5) == 5


def test_condition_comparators():
    assert evaluate_condition(DOC, {"gte": [{"ref": "handoff.amount"}, 4000]}) is True
    assert evaluate_condition(DOC, {"lt": [{"ref": "handoff.amount"}, 4000]}) is False
    assert evaluate_condition(DOC, {"eq": [{"ref": "handoff.currency"}, "USD"]}) is True


def test_condition_boolean_combinators():
    cond = {"any": [{"lt": [{"ref": "handoff.amount"}, 0]}, {"eq": [{"ref": "handoff.currency"}, "USD"]}]}
    assert evaluate_condition(DOC, cond) is True
    assert evaluate_condition(DOC, {"all": [{"gte": [{"ref": "handoff.amount"}, 4000]}, {"lt": [{"ref": "handoff.amount"}, 5000]}]}) is True
    assert evaluate_condition(DOC, {"not": {"eq": [{"ref": "handoff.currency"}, "EUR"]}}) is True


def test_condition_missing_operand_is_safe():
    # A missing left operand can never satisfy an ordering comparison.
    assert evaluate_condition(DOC, {"gte": [{"ref": "handoff.ghost"}, 1]}) is False
    assert evaluate_condition(DOC, {"ne": [{"ref": "handoff.ghost"}, 1]}) is True


def test_condition_rejects_unknown_operator():
    with pytest.raises(ContractError):
        evaluate_condition(DOC, {"approximately": [1, 1]})
