"""SeamProof — the seam tester for agentic processes.

SeamProof treats every handoff in an agentic process (AI agent -> RPA robot ->
human approver) as a *contract* and tests it against the real run trace. It
catches the failures that emerge at the seams between actors — the ones that
isolated agent evals and unit tests never see — and emits a go/no-go release
gate with the evidence.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .contracts import Boundary, Contract, load_contract, load_contracts
from .evaluators import AssertionResult, ContractResult, evaluate_contract
from .gate import Decision, GateResult, evaluate_gate
from .trace import Event, Trace

__all__ = [
    "__version__",
    "Boundary",
    "Contract",
    "load_contract",
    "load_contracts",
    "AssertionResult",
    "ContractResult",
    "evaluate_contract",
    "Decision",
    "GateResult",
    "evaluate_gate",
    "Event",
    "Trace",
]
