"""SeamProof — the seam tester for agentic processes.

SeamProof treats every handoff in an agentic process (AI agent -> RPA robot ->
human approver) as a *contract* and tests it against the real run trace. It
catches the failures that emerge at the seams between actors — the ones that
isolated agent evals and unit tests never see — and emits a go/no-go release
gate with the evidence.
"""
from __future__ import annotations

from ._version import __version__
from .contracts import Boundary, Contract, load_contract, load_contracts
from .evaluators import AssertionResult, ContractResult, evaluate_contract
from .gate import Decision, GateResult, evaluate_gate
from .ingest import otel_to_trace, trace_from_otel
from .publish import PublishConfig, build_payload, publish
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
    "otel_to_trace",
    "trace_from_otel",
    "PublishConfig",
    "build_payload",
    "publish",
    "Event",
    "Trace",
]
