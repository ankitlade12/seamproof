"""Render a gate result for humans and for machines.

Four formats, one source of truth:

* ``text``     — coloured console output (the demo "money shot").
* ``markdown`` — drops straight into a PR comment or a Devpost write-up.
* ``json``     — the full result for downstream tooling.
* ``junit``    — JUnit XML so the gate shows up natively in UiPath Test Manager
                 or any CI test view.
"""
from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING
from xml.dom import minidom
from xml.etree import ElementTree as ET

from .evaluators import ContractResult
from .gate import GateResult

if TYPE_CHECKING:
    from .analyst import Recommendation

_PASS = "PASS"
_FAIL = "FAIL"


class _Style:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def green(self, t: str) -> str:
        return self._wrap("32", t)

    def red(self, t: str) -> str:
        return self._wrap("31", t)

    def yellow(self, t: str) -> str:
        return self._wrap("33", t)

    def bold(self, t: str) -> str:
        return self._wrap("1", t)

    def dim(self, t: str) -> str:
        return self._wrap("2", t)


def _color_enabled(stream) -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("SEAMPROOF_FORCE_COLOR") is not None:
        return True
    return hasattr(stream, "isatty") and stream.isatty()


def render(
    result: GateResult,
    fmt: str = "text",
    *,
    color: bool | None = None,
    recommendations: list[Recommendation] | None = None,
) -> str:
    if fmt == "text":
        return render_text(result, color=color, recommendations=recommendations)
    if fmt == "markdown":
        return render_markdown(result, recommendations=recommendations)
    if fmt == "json":
        return render_json(result, recommendations=recommendations)
    if fmt == "junit":
        return render_junit(result)
    raise ValueError(f"unknown report format: {fmt!r}")


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #

def render_text(
    result: GateResult, *, color: bool | None = None,
    recommendations: list[Recommendation] | None = None,
) -> str:
    enabled = _color_enabled(sys.stdout) if color is None else color
    s = _Style(enabled)
    lines: list[str] = []
    lines.append(s.bold(f"SeamProof — {result.trace.process}"))
    lines.append(s.dim(f"trace {result.trace.trace_id} · {len(result.results)} seam contracts"))
    lines.append("")

    for cr in result.results:
        seam_passed = cr.passed
        badge = s.green(_PASS) if seam_passed else s.red(_FAIL)
        tag = "" if cr.contract.blocking else s.yellow(" [advisory]")
        lines.append(f"{badge}  {s.bold(cr.contract.name)}{tag}")
        lines.append(s.dim(f"      seam {cr.contract.id} · {cr.contract.boundary}"))
        for a in cr.assertions:
            mark = s.green("  ✓") if a.passed else s.red("  ✗")
            lines.append(f"    {mark} {a.id}")
            if not a.passed:
                lines.append(s.dim(f"        {a.detail}"))
        lines.append("")

    decision = result.decision
    summary = (
        f"{result.total_assertions - result.failed_assertions}/{result.total_assertions} "
        "assertions passed"
    )
    if decision.is_go:
        lines.append(s.green(s.bold(f"GATE: GO  —  {summary}")))
    else:
        seams = ", ".join(cr.contract.id for cr in result.blocking_failures)
        lines.append(s.red(s.bold(f"GATE: NO-GO  —  release blocked by {seams}")))
        lines.append(s.dim(f"       {summary}"))
    if result.advisory_failures:
        seams = ", ".join(cr.contract.id for cr in result.advisory_failures)
        lines.append(s.yellow(f"       advisory: {seams} regressed (not blocking)"))

    if recommendations:
        lines.append("")
        lines.append(s.bold("Seam Analyst — recommendations") + s.dim(f"  ({recommendations[0].source})"))
        for r in recommendations:
            frag = {"high": s.red, "medium": s.yellow}.get(r.fragility, s.green)(r.fragility)
            lines.append(f"  {s.bold(r.seam_id)} {s.dim('· ' + r.boundary)}  [fragility: {frag}]")
            lines.append(s.dim(f"      root cause: {r.root_cause}"))
            lines.append(f"      {s.green('fix:')} {r.recommended_fix}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# markdown
# --------------------------------------------------------------------------- #

def render_markdown(
    result: GateResult, *, recommendations: list[Recommendation] | None = None
) -> str:
    decision = result.decision
    head = "✅ **GATE: GO**" if decision.is_go else "🚫 **GATE: NO-GO**"
    lines = [f"## SeamProof — {head}", ""]
    lines.append(f"`{result.trace.process}` · trace `{result.trace.trace_id}`")
    lines.append("")
    lines.append("| Seam | Boundary | Result | Failed checks |")
    lines.append("| --- | --- | --- | --- |")
    for cr in result.results:
        status = "PASS ✅" if cr.passed else ("FAIL 🚫" if cr.contract.blocking else "FAIL ⚠️")
        failed = ", ".join(a.id for a in cr.failures) or "—"
        lines.append(f"| `{cr.contract.id}` | {cr.contract.boundary} | {status} | {failed} |")
    lines.append("")
    for cr in result.results:
        for a in cr.failures:
            lines.append(f"- **{cr.contract.id} / {a.id}** — {a.detail}")
    if recommendations:
        lines.append("")
        lines.append(f"### 🔧 Seam Analyst — recommendations _({recommendations[0].source})_")
        for r in recommendations:
            lines.append(f"- **`{r.seam_id}`** ({r.boundary}) · fragility **{r.fragility}**")
            lines.append(f"  - **Root cause:** {r.root_cause}")
            lines.append(f"  - **Fix:** {r.recommended_fix}")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# json
# --------------------------------------------------------------------------- #

def _contract_payload(cr: ContractResult) -> dict:
    return {
        "seam": cr.contract.id,
        "name": cr.contract.name,
        "boundary": {"from": cr.contract.boundary.source, "to": cr.contract.boundary.target},
        "severity": cr.contract.severity,
        "passed": cr.passed,
        "assertions": [
            {
                "id": a.id,
                "kind": a.kind,
                "passed": a.passed,
                "description": a.description,
                "detail": a.detail,
                "evidence": a.evidence,
            }
            for a in cr.assertions
        ],
    }


def render_json(
    result: GateResult, *, recommendations: list[Recommendation] | None = None
) -> str:
    payload = {
        "process": result.trace.process,
        "trace_id": result.trace.trace_id,
        "decision": result.decision.value,
        "summary": {
            "total_assertions": result.total_assertions,
            "failed_assertions": result.failed_assertions,
            "blocking_failures": [cr.contract.id for cr in result.blocking_failures],
            "advisory_failures": [cr.contract.id for cr in result.advisory_failures],
        },
        "seams": [_contract_payload(cr) for cr in result.results],
    }
    if recommendations is not None:
        payload["recommendations"] = [r.as_dict() for r in recommendations]
    return json.dumps(payload, indent=2)


# --------------------------------------------------------------------------- #
# junit
# --------------------------------------------------------------------------- #

def render_junit(result: GateResult) -> str:
    suites = ET.Element("testsuites", name="SeamProof")
    total_failures = 0
    total_tests = 0
    for cr in result.results:
        failures = len(cr.failures)
        total_failures += failures
        total_tests += len(cr.assertions)
        suite = ET.SubElement(
            suites,
            "testsuite",
            name=f"{cr.contract.id} {cr.contract.name}",
            tests=str(len(cr.assertions)),
            failures=str(failures),
        )
        for a in cr.assertions:
            case = ET.SubElement(
                suite,
                "testcase",
                classname=f"seam.{cr.contract.id}",
                name=a.id,
            )
            if not a.passed:
                failure = ET.SubElement(
                    case,
                    "failure",
                    message=a.detail,
                    type="advisory" if not cr.contract.blocking else "contract-violation",
                )
                failure.text = a.detail
    suites.set("tests", str(total_tests))
    suites.set("failures", str(total_failures))
    rough = ET.tostring(suites, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ")
