"""Loading and modelling seam contracts.

A *seam contract* is the set of properties the **receiving** actor at a boundary
depends on. SeamProof treats the boundary as an interface and the contract as its
specification: if the trace shows the contract was honoured, the seam held; if
not, the seam failed and the release is gated.

Contracts are plain YAML (or JSON) so they read as policy and diff cleanly in
review.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ContractError

# A failing assertion on a *blocking* contract stops the release. An *advisory*
# contract still reports failures (e.g. an SLO drift) but does not block.
SEVERITIES = ("blocking", "advisory")


@dataclass(frozen=True)
class Boundary:
    source: str  # actor handing off, e.g. "recon-agent"
    target: str  # actor receiving, e.g. "posting-robot"

    def __str__(self) -> str:
        return f"{self.source} -> {self.target}"


@dataclass
class Contract:
    """One seam's contract: where it lives and what must hold across it."""

    id: str
    name: str
    boundary: Boundary
    assertions: list[dict[str, Any]]
    description: str = ""
    severity: str = "blocking"
    # How to locate the payload that crosses the boundary within a trace.
    handoff: dict[str, Any] = field(default_factory=dict)
    source_path: Path | None = None

    @property
    def blocking(self) -> bool:
        return self.severity == "blocking"

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_path: Path | None = None) -> Contract:
        for required in ("id", "name", "boundary", "assertions"):
            if required not in data:
                raise ContractError(f"contract is missing required field '{required}'")

        boundary = data["boundary"]
        if not isinstance(boundary, dict) or "from" not in boundary or "to" not in boundary:
            raise ContractError("contract.boundary must define 'from' and 'to'")

        severity = data.get("severity", "blocking")
        if severity not in SEVERITIES:
            raise ContractError(f"contract.severity must be one of {SEVERITIES}, got {severity!r}")

        assertions = data["assertions"]
        if not isinstance(assertions, list) or not assertions:
            raise ContractError("contract.assertions must be a non-empty list")
        for index, assertion in enumerate(assertions):
            if "kind" not in assertion:
                raise ContractError(f"assertion #{index} is missing 'kind'")
            assertion.setdefault("id", f"{data['id']}-{index}")

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            boundary=Boundary(str(boundary["from"]), str(boundary["to"])),
            assertions=assertions,
            description=str(data.get("description", "")),
            severity=severity,
            handoff=dict(data.get("handoff", {})),
            source_path=source_path,
        )


def _read(path: Path) -> dict[str, Any]:
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        raise ContractError(f"unsupported contract format: {path.suffix} ({path})")
    if not isinstance(data, dict):
        raise ContractError(f"contract {path} must be a mapping at the top level")
    return data


def load_contract(path: str | Path) -> Contract:
    p = Path(path)
    return Contract.from_dict(_read(p), source_path=p)


def load_contracts(path: str | Path) -> list[Contract]:
    """Load a single contract file or every contract in a directory."""
    p = Path(path)
    if p.is_dir():
        files = sorted(
            f for f in p.iterdir() if f.suffix.lower() in (".yaml", ".yml", ".json")
        )
        if not files:
            raise ContractError(f"no contract files found in {p}")
        return [load_contract(f) for f in files]
    if not p.exists():
        raise ContractError(f"contracts path not found: {p}")
    return [load_contract(p)]
