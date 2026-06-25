"""The release gate.

The gate is the product's verdict. It aggregates every contract result for one
run trace into a single decision — **GO** or **NO-GO** — and explains why. A
failure on a *blocking* seam vetoes the release; an *advisory* seam (typically a
cost or cycle-time SLO) surfaces as a warning without blocking.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .contracts import Contract
from .evaluators import ContractResult, evaluate_contract
from .trace import Trace


class Decision(str, Enum):
    GO = "GO"
    NO_GO = "NO-GO"

    @property
    def is_go(self) -> bool:
        return self is Decision.GO


@dataclass
class GateResult:
    trace: Trace
    results: list[ContractResult]

    @property
    def decision(self) -> Decision:
        for result in self.results:
            if result.contract.blocking and not result.passed:
                return Decision.NO_GO
        return Decision.GO

    @property
    def blocking_failures(self) -> list[ContractResult]:
        return [r for r in self.results if r.contract.blocking and not r.passed]

    @property
    def advisory_failures(self) -> list[ContractResult]:
        return [r for r in self.results if not r.contract.blocking and not r.passed]

    @property
    def total_assertions(self) -> int:
        return sum(len(r.assertions) for r in self.results)

    @property
    def failed_assertions(self) -> int:
        return sum(len(r.failures) for r in self.results)

    @property
    def exit_code(self) -> int:
        return 0 if self.decision.is_go else 1


def evaluate_gate(trace: Trace, contracts: list[Contract]) -> GateResult:
    results = [evaluate_contract(trace, contract) for contract in contracts]
    return GateResult(trace=trace, results=results)
