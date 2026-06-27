"""The Seam Analyst — the agent that explains and fixes a failed seam.

Deterministic assertions tell you *that* a seam failed. The Seam Analyst tells you
*why* and *how to fix it*: for each failed seam it produces a root-cause hypothesis,
a concrete recommended fix, and a fragility rating. It runs as a UiPath **LLM Gateway**
agent (the same AI Trust Layer the system under test uses) when credentials are
present, and falls back to a deterministic heuristic offline — so it degrades like the
rest of SeamProof.

This is the Track-3 "agent that recommends fixes" on the *testing* side: the tester is
no longer only a gate; it reasons about the failures it finds and hands the developer a
remediation, while the deterministic gate stays the source of truth for go/no-go.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from .evaluators import ContractResult
from .gate import GateResult

# The LLM Gateway's default; chat_completions picks its own if this is omitted.
DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"

_SYSTEM = (
    "You are the Seam Analyst, a test-failure analyst for agentic business processes "
    "running on UiPath. A 'seam' is a handoff between an AI agent, an RPA robot, and a "
    "human approver; a seam contract asserts what must hold as work crosses that "
    "boundary. A seam has just failed its contract. From the boundary, the failed "
    "checks, and the evidence, give: the most likely ROOT CAUSE in the process itself "
    "(not in the test); a CONCRETE recommended fix a developer can act on; and a "
    "FRAGILITY rating (low, medium, or high) for the seam with a one-sentence reason. "
    "Be specific and concise. Respond as JSON with exactly these keys: "
    '{"root_cause", "recommended_fix", "fragility", "fragility_reason"}.'
)


@dataclass
class Recommendation:
    """The Seam Analyst's verdict on one failed seam."""

    seam_id: str
    seam_name: str
    boundary: str
    severity: str
    root_cause: str
    recommended_fix: str
    fragility: str
    fragility_reason: str
    source: str  # "llm-gateway" | "heuristic"

    @property
    def reason_line(self) -> str:
        """A compact one-liner suitable for a Test Manager result reason."""
        return f"Root cause: {self.root_cause} ▸ Recommended fix: {self.recommended_fix}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "seam": self.seam_id,
            "boundary": self.boundary,
            "severity": self.severity,
            "root_cause": self.root_cause,
            "recommended_fix": self.recommended_fix,
            "fragility": self.fragility,
            "fragility_reason": self.fragility_reason,
            "source": self.source,
        }


# --------------------------------------------------------------------------- #
# Heuristic analyst (always available, offline)
# --------------------------------------------------------------------------- #

def _evidence_str(cr: ContractResult) -> str:
    bits: list[str] = []
    for a in cr.failures:
        ev = {k: v for k, v in (a.evidence or {}).items() if v is not None}
        kv = ", ".join(f"{k}={v!r}" for k, v in ev.items())
        bits.append(f"{a.id} [{a.kind}]: {a.detail}" + (f" ({kv})" if kv else ""))
    return "; ".join(bits)


def _heuristic(cr: ContractResult) -> Recommendation:
    """A deterministic recommendation derived from the failing assertion kinds."""
    kinds = {a.kind for a in cr.failures}
    src, tgt = cr.contract.boundary.source, cr.contract.boundary.target
    boundary = str(cr.contract.boundary)
    evidence = _evidence_str(cr)

    # Default: a data/property seam.
    root = f"The contract across {boundary} was violated — {evidence or 'a required property did not hold'}."
    fix = (f"Re-derive the disputed value from its source of truth before {tgt} consumes it, "
           "and add a post-condition that blocks the handoff on mismatch.")
    fragility, why = "high", "A single structurally-valid but wrong value reaches the next actor unchecked."

    if "requires_event" in kinds:
        root = (f"A required checkpoint between {src} and {tgt} was missing or out of order — "
                "output variability let the work route around it.")
        fix = (f"Make the checkpoint unconditional in the router (a default-deny gateway) and assert the "
               f"approval event occurs before {tgt} acts.")
        fragility, why = "high", "Routing variability can skip a policy-required human approval."
    elif "range" in kinds:
        root = f"A non-functional budget across {boundary} drifted out of range — {evidence}."
        fix = ("Profile the prompt/model change that moved the metric; tune it or raise the budget "
               "deliberately, and alert on sustained drift.")
        fragility, why = "medium", "Cost/latency drift is gradual and easy to miss without a budget assertion."
    elif "equals" in kinds:
        root = (f"The value handed from {src} to {tgt} disagrees with its source of truth — {evidence}. "
                "The upstream actor likely extracted or computed it incorrectly.")
        fix = (f"Recompute the value from the source of truth before {tgt} consumes it, or add a "
               "reconciliation post-condition that blocks the handoff on mismatch.")
        fragility, why = "high", "Structurally-valid but semantically-wrong output passes schema checks and reaches the robot."

    if not cr.contract.blocking and fragility == "high":
        fragility = "medium"

    return Recommendation(
        seam_id=cr.contract.id, seam_name=cr.contract.name, boundary=boundary,
        severity=cr.contract.severity, root_cause=root, recommended_fix=fix,
        fragility=fragility, fragility_reason=why, source="heuristic",
    )


# --------------------------------------------------------------------------- #
# LLM Gateway analyst (AI Trust Layer)
# --------------------------------------------------------------------------- #

def _user_prompt(cr: ContractResult, process: str) -> str:
    checks = "\n  ".join(
        f"{a.id} [{a.kind}]: {a.detail}"
        + (f"  evidence={json.dumps(a.evidence)}" if a.evidence else "")
        for a in cr.failures
    )
    return (
        f"Process: {process}\n"
        f"Seam: {cr.contract.id} — {cr.contract.name}\n"
        f"Boundary: {cr.contract.boundary} (severity: {cr.contract.severity})\n"
        f"What the seam guards: {cr.contract.description or cr.contract.boundary}\n"
        f"Failed checks:\n  {checks}\n\n"
        "Return the JSON."
    )


def _llm(cr: ContractResult, process: str, model: str | None) -> Recommendation:
    """Analyse via the UiPath LLM Gateway. Raises on any failure (caller falls back)."""
    from uipath.platform import UiPath

    client = UiPath()
    kwargs: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _user_prompt(cr, process)},
        ],
        "response_format": {"type": "json_object"},
    }
    if model:
        kwargs["model"] = model
    response = client.llm.chat_completions(**kwargs)
    content = (
        response.choices[0].message.content
        if hasattr(response, "choices")
        else response["choices"][0]["message"]["content"]
    )
    data = json.loads(content)
    frag = str(data.get("fragility", "medium")).strip().lower()
    return Recommendation(
        seam_id=cr.contract.id, seam_name=cr.contract.name, boundary=str(cr.contract.boundary),
        severity=cr.contract.severity,
        root_cause=str(data.get("root_cause", "")).strip() or "(no root cause returned)",
        recommended_fix=str(data.get("recommended_fix", "")).strip() or "(no fix returned)",
        fragility=frag if frag in ("low", "medium", "high") else "medium",
        fragility_reason=str(data.get("fragility_reason", "")).strip(),
        source="llm-gateway",
    )


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #

def llm_available() -> bool:
    """True when the UiPath SDK and credentials are present to reach the LLM Gateway."""
    if not (os.environ.get("UIPATH_URL") or os.environ.get("UIPATH_ACCESS_TOKEN")):
        return False
    try:
        import uipath.platform  # noqa: F401
        return True
    except Exception:
        return False


def recommend(
    cr: ContractResult, *, process: str = "", use_llm: bool | None = None, model: str | None = None
) -> Recommendation:
    """Recommend a fix for one failed seam, via the LLM Gateway or the heuristic."""
    want_llm = llm_available() if use_llm is None else use_llm
    if want_llm:
        try:
            return _llm(cr, process, model)
        except Exception:
            pass  # the heuristic always works — never let analysis break the gate
    return _heuristic(cr)


def analyze(
    result: GateResult, *, use_llm: bool | None = None, model: str | None = None
) -> list[Recommendation]:
    """One recommendation per failed seam (blocking or advisory). Empty on a clean GO."""
    return [
        recommend(cr, process=result.trace.process, use_llm=use_llm, model=model)
        for cr in result.results
        if not cr.passed
    ]
