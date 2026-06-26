"""Invoice-exception process — a UiPath coded automation (the SeamProof SUT).

This is a real UiPath coded automation: the entrypoint ``process`` takes a
dataclass input and is declared in ``uipath.json``. Each step is instrumented
with UiPath's ``@traced`` decorator, so running it in the tenant produces native
UiPath/Maestro traces; the recon step calls the UiPath **LLM Gateway**
(AI Trust Layer) when credentials are present. It also emits a standard
**OpenTelemetry** (OTLP/JSON) document of the run, which SeamProof ingests and
gates.

Run in the tenant:
    uipath auth
    uipath run process '{"case": "seam1_corruption"}'

Run offline (no tenant needed — deterministic recon, OTLP written to a file):
    python main.py seam1_corruption            # writes seam1_corruption.otlp.json
    seamproof check -c ../../contracts --otel seam1_corruption.otlp.json

The three cases mirror sut/data/invoices.json:
    golden              -> GATE: GO
    seam1_corruption    -> NO-GO (seam-1: amount != sum(line_items))
    seam2_near_ceiling  -> NO-GO (seam-2: skipped human checkpoint)
"""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# Real UiPath tracing when the SDK is installed; a no-op shim offline so the
# automation stays runnable and testable without the platform.
try:
    from uipath.tracing import traced
except Exception:  # pragma: no cover - exercised in the core (no-uipath) environment
    def traced(name: Any = None, **_kwargs: Any):
        def _wrap(fn):
            return fn
        return _wrap(name) if callable(name) else _wrap


# --------------------------------------------------------------------------- #
# Process policy and test inputs (mirrors sut/data/invoices.json)
# --------------------------------------------------------------------------- #

CONTEXT: dict[str, Any] = {
    "approved_vendor_master": ["V-1042", "V-1043", "V-2001", "V-3300"],
    "auto_post_ceiling": 10000,
    "human_review_floor": 9000,
    "min_confidence": 0.90,
    "sla": {"max_cost_usd": 0.05, "max_cycle_seconds": 120},
}

CASES: dict[str, dict[str, Any]] = {
    "golden": {
        "trace_id": "sut-golden-001",
        "route_mode": "policy",
        "invoice_text": (
            "INVOICE\nVendor: Acme Supplies (V-1042)\nCurrency: USD\nLine items:\n"
            "  A1  Widget assembly ......  1,200.00\n  B2  Gadget kit ...........  3,000.00\n"
            "TOTAL DUE: USD 4,200.00"
        ),
        "po": {"number": "PO-88231", "currency": "USD", "vendor_id": "V-1042", "amount": 4200.00},
        "receipt": {"received": True, "items": ["A1", "B2"]},
    },
    "seam1_corruption": {
        "trace_id": "sut-seam1-001",
        "route_mode": "policy",
        "invoice_text": (
            "INVOICE\nVendor: Acme Supplies (V-1042)\nCurrency: USD\nLine items:\n"
            "  A1  Widget assembly ......  1,200.00\n  B2  Gadget kit ...........  3,000.00\n"
            "TOTAL DUE: USD 5,400.00"
        ),
        "po": {"number": "PO-88231", "currency": "USD", "vendor_id": "V-1042", "amount": 4200.00},
        "receipt": {"received": True, "items": ["A1", "B2"]},
    },
    "seam2_near_ceiling": {
        "trace_id": "sut-seam2-001",
        # The (mis)configured gateway that only checks the hard ceiling — the bug
        # SeamProof catches, since policy required a human at the 9,000 floor.
        "route_mode": "ceiling_only",
        "invoice_text": (
            "INVOICE\nVendor: Northwind Traders (V-2001)\nCurrency: USD\nLine items:\n"
            "  E5  Server rack ..........  4,950.00\n  F6  Network switch .......  5,000.00\n"
            "TOTAL DUE: USD 9,950.00"
        ),
        "po": {"number": "PO-77450", "currency": "USD", "vendor_id": "V-2001", "amount": 9950.00},
        "receipt": {"received": True, "items": ["E5", "F6"]},
    },
    "high_value": {
        # Correctly routed to a human (amount >= review floor) and approved before
        # posting — the happy path that exercises the Action Center step.
        "trace_id": "sut-highval-001",
        "route_mode": "policy",
        "invoice_text": (
            "INVOICE\nVendor: Acme Supplies (V-1043)\nCurrency: USD\nLine items:\n"
            "  C3  Server cluster ......  7,000.00\n  D4  Support plan ........  5,000.00\n"
            "TOTAL DUE: USD 12,000.00"
        ),
        "po": {"number": "PO-90115", "currency": "USD", "vendor_id": "V-1043", "amount": 12000.00},
        "receipt": {"received": True, "items": ["C3", "D4"]},
    },
}

_RECON_SYSTEM = (
    "You are an accounts-payable reconciliation agent. Extract the vendor id, the "
    "invoice TOTAL exactly as printed (do not recompute it from the line items), the "
    "currency, and each line item. Set confidence in [0,1]. Set exception_flagged to "
    "true only on a vendor, currency, or receipt discrepancy. Return JSON with keys: "
    "vendor_id, amount, currency, line_items (list of {sku, amount}), confidence, "
    "exception_flagged."
)


@dataclass
class ProcessInput:
    case: str = "golden"
    use_llm: bool = False               # recon via the UiPath LLM Gateway
    use_action_center: bool = False     # create a real Action Center task at the human step
    route_mode: str | None = None       # override the case's routing mode
    out: str | None = None              # write the OTLP doc here when set


@dataclass
class ProcessOutput:
    trace_id: str
    route: str
    posted: bool
    posted_amount: float
    otlp: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Steps (each emits a UiPath trace span via @traced)
# --------------------------------------------------------------------------- #

def _parse_money(text: str) -> float:
    return float(text.replace(",", ""))


def _deterministic_recon(invoice_text: str, po: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    vendor = re.search(r"\((V-\d+)\)", invoice_text)
    currency = re.search(r"Currency:\s*([A-Z]{3})", invoice_text)
    total = re.search(r"TOTAL DUE:\s*[A-Z]{3}\s*([\d,]+\.\d{2})", invoice_text)
    items = re.findall(r"^\s+([A-Za-z]\d+)\s+.+?([\d,]+\.\d{2})\s*$", invoice_text, re.MULTILINE)
    vendor_id = vendor.group(1) if vendor else "UNKNOWN"
    cur = currency.group(1) if currency else po.get("currency", "USD")
    exception = (
        vendor_id not in CONTEXT["approved_vendor_master"]
        or cur != po.get("currency")
        or not receipt.get("received", False)
    )
    return {
        "vendor_id": vendor_id,
        "amount": _parse_money(total.group(1)) if total else 0.0,
        "currency": cur,
        "line_items": [{"sku": sku, "amount": _parse_money(amt)} for sku, amt in items],
        "confidence": 0.95,
        "exception_flagged": exception,
    }


def _llm_recon(invoice_text: str, po: dict[str, Any], model: str | None) -> dict[str, Any]:
    """Reconcile via the UiPath LLM Gateway (AI Trust Layer). Raises on any failure."""
    from uipath.platform import UiPath

    client = UiPath()
    user = f"Invoice:\n{invoice_text}\n\nPurchase order:\n{json.dumps(po)}\n\nReturn the JSON."
    kwargs: dict[str, Any] = {
        "messages": [{"role": "system", "content": _RECON_SYSTEM}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    if model:
        kwargs["model"] = model
    response = client.llm.chat_completions(**kwargs)
    content = response.choices[0].message.content if hasattr(response, "choices") else (
        response["choices"][0]["message"]["content"]
    )
    return json.loads(content)


@traced(name="reconcile", span_type="agent")
def reconcile(case: dict[str, Any], use_llm: bool, model: str | None = None) -> dict[str, Any]:
    """The recon agent: extract and reconcile the invoice (agent.output)."""
    if use_llm:
        try:
            return _llm_recon(case["invoice_text"], case["po"], model)
        except Exception:
            pass  # fall back to the deterministic extractor offline / on any gateway error
    return _deterministic_recon(case["invoice_text"], case["po"], case["receipt"])


@traced(name="route", span_type="decision")
def route(recon: dict[str, Any], route_mode: str) -> dict[str, Any]:
    """The router: decide auto-post vs human review (routing.decision)."""
    if route_mode == "ceiling_only":
        needs_human = recon["amount"] >= CONTEXT["auto_post_ceiling"]
        reason = "ceiling-only gateway (amount < hard ceiling -> auto-post)"
    else:
        needs_human = (
            recon["amount"] >= CONTEXT["human_review_floor"]
            or recon["confidence"] < CONTEXT["min_confidence"]
            or recon["exception_flagged"]
        )
        reason = "policy gateway (review floor / confidence / exception)"
    return {"route": "human-review" if needs_human else "auto-post", "reason": reason, "mode": route_mode}


def _create_action_center_task(recon: dict[str, Any]) -> str | None:
    """Create a real UiPath Action Center task and return its key (tenant mode).

    In a Maestro-orchestrated run the process *suspends* on this task (the
    ``WaitTask`` interrupt) until a human acts, then resumes. Here we create the
    task so it is visible and actionable in Action Center, and record its key.
    """
    from uipath.platform import UiPath

    client = UiPath()
    task = client.tasks.create(
        title=f"Approve invoice {recon['vendor_id']} — {recon['currency']} {recon['amount']:,.2f}",
        data={k: recon[k] for k in ("vendor_id", "amount", "currency")},
        priority="Medium",
    )
    return str(getattr(task, "key", None) or getattr(task, "id", "") or "") or None


@traced(name="approve", span_type="human")
def approve(recon: dict[str, Any], use_action_center: bool = False) -> dict[str, Any]:
    """The human approver via Action Center (human.decision)."""
    decision = {"status": "approved", "approver": "j.okafor", "note": "PO and receipt match"}
    if use_action_center:
        try:
            key = _create_action_center_task(recon)
            if key:
                decision["action_center_task"] = key
        except Exception:
            pass  # offline / no credentials -> simulated approval
    return decision


@traced(name="post_invoice", span_type="robot")
def post_invoice(recon: dict[str, Any], erp_url: str | None = None) -> dict[str, Any]:
    """The posting robot: write the approved invoice to the ERP (robot.action)."""
    if erp_url:
        import urllib.request

        body = json.dumps({"vendor_id": recon["vendor_id"], "amount": recon["amount"]}).encode()
        req = urllib.request.Request(erp_url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            status = "success" if resp.status < 400 else "error"
    else:
        status = "success"
    return {"system": "mock-erp", "operation": "post_invoice", "status": status, "posted_amount": recon["amount"]}


# --------------------------------------------------------------------------- #
# OTLP emission (so SeamProof can gate the run)
# --------------------------------------------------------------------------- #

def _anyvalue(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_anyvalue(v) for v in value]}}
    if isinstance(value, dict):
        return {"kvlistValue": {"values": [{"key": k, "value": _anyvalue(v)} for k, v in value.items()]}}
    return {"stringValue": str(value)}


def _attrs(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"key": k, "value": _anyvalue(v)} for k, v in data.items()]


def _otlp(trace_id: str, spans: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    base = time.time_ns()
    otlp_spans = []
    for index, (name, attributes) in enumerate(spans):
        otlp_spans.append(
            {
                "traceId": trace_id,
                "spanId": f"{index + 1:016x}",
                "name": name,
                "startTimeUnixNano": str(base + index * 1_000_000_000),
                "endTimeUnixNano": str(base + index * 1_000_000_000 + 500_000_000),
                "attributes": _attrs(attributes),
            }
        )
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": _attrs(
                        {"service.name": "invoice-exception-handling", "uipath.product": "maestro"}
                    )
                },
                "scopeSpans": [{"scope": {"name": "seamproof.sut"}, "spans": otlp_spans}],
            }
        ]
    }


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #

@traced(name="invoice-exception-process")
def process(input: ProcessInput) -> ProcessOutput:
    case = CASES.get(input.case)
    if case is None:
        raise ValueError(f"unknown case {input.case!r}; choose from {list(CASES)}")
    route_mode = input.route_mode or case["route_mode"]

    recon = reconcile(case, input.use_llm)
    routing = route(recon, route_mode)

    spans: list[tuple[str, dict[str, Any]]] = [
        ("run.context", {**CONTEXT, "po": case["po"]}),
        ("agent.output", {"actor": "recon-agent", "actor_type": "agent", **recon}),
        ("routing.decision", {"actor": "router", "actor_type": "router", **routing}),
    ]
    if routing["route"] == "human-review":
        decision = approve(recon, input.use_action_center)
        spans.append(("human.decision", {"actor": "approver", "actor_type": "human", **decision}))

    robot_input = {
        "actor": "posting-robot", "actor_type": "robot",
        "vendor_id": recon["vendor_id"], "amount": recon["amount"],
        "currency": recon["currency"], "line_items": recon["line_items"],
    }
    action = post_invoice(recon, getattr(input, "erp_url", None))
    spans.append(("robot.input", robot_input))
    spans.append(("robot.action", {"actor": "posting-robot", "actor_type": "robot", **action}))
    spans.append(("run.metrics", {"actor": "system", "actor_type": "system",
                                   "cost_usd": 0.012, "cycle_seconds": 42, "model": "uipath-llm-gateway"}))

    otlp = _otlp(case["trace_id"], spans)
    if input.out:
        with open(input.out, "w") as fh:
            json.dump(otlp, fh, indent=2)
    return ProcessOutput(
        trace_id=case["trace_id"],
        route=routing["route"],
        posted=action["status"] == "success",
        posted_amount=action["posted_amount"],
        otlp=otlp,
    )


@dataclass
class ExtractInput:
    case: str = "golden"
    use_llm: bool = False


@traced(name="extract")
def extract(input: ExtractInput) -> dict[str, Any]:
    """Recon-only entrypoint, used by `uipath eval` to quality-test the agent."""
    case = CASES.get(input.case)
    if case is None:
        raise ValueError(f"unknown case {input.case!r}; choose from {list(CASES)}")
    return reconcile(case, input.use_llm)


if __name__ == "__main__":
    case_name = sys.argv[1] if len(sys.argv) > 1 else "golden"
    out_path = sys.argv[2] if len(sys.argv) > 2 else f"{case_name}.otlp.json"
    result = process(ProcessInput(case=case_name, out=out_path))
    print(f"case={case_name} route={result.route} posted={result.posted} "
          f"amount={result.posted_amount} -> {out_path}")
