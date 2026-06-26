"""LangChain recon extractor — the external-framework path.

This is the cross-platform integration: an external **LangChain** chain
(`prompt | llm | JSON parser`) does the invoice reconciliation, and the default
model is **UiPathChat** — the UiPath LLM Gateway (AI Trust Layer) exposed as a
LangChain chat model via `uipath-langchain`. So a LangChain agent runs *through*
UiPath and can be orchestrated by Maestro, while remaining swappable for any
LangChain provider (`ChatAnthropic`, `ChatOpenAI`, …) by injecting a different
`llm`.

The chain output matches the same schema the deterministic/Gateway recon emits,
so SeamProof gates it identically.
"""
from __future__ import annotations

import json
from typing import Any

_SYSTEM = (
    "You are an accounts-payable reconciliation agent. From the invoice and its "
    "purchase order, extract the vendor id, the invoice TOTAL exactly as printed "
    "(do not recompute it from the line items), the currency, and each line item. "
    "Set confidence in [0,1]. Set exception_flagged true only on a vendor, "
    "currency, or receipt discrepancy. Respond with ONLY a JSON object with keys: "
    "vendor_id, amount, currency, line_items (list of {{sku, amount}}), confidence, "
    "exception_flagged."
)


def build_chain(llm: Any):
    """Compose the LangChain runnable: prompt | llm | JSON parser."""
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _SYSTEM),
            ("human", "Invoice:\n{invoice_text}\n\nPurchase order:\n{po}\n\nReturn the JSON."),
        ]
    )
    return prompt | llm | JsonOutputParser()


def default_llm() -> Any:
    """The UiPath LLM Gateway as a LangChain chat model (needs `uipath auth`)."""
    from uipath_langchain.chat.models import UiPathChat

    return UiPathChat(model="gpt-4o-mini-2024-07-18")


def _to_float(value: Any) -> Any:
    """Coerce a model-formatted amount (e.g. "5,400.00") to a float."""
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("$", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return value
    return value


def _normalize(recon: dict[str, Any]) -> dict[str, Any]:
    """Coerce numeric fields so the LLM's output matches the seam-contract schema."""
    recon["amount"] = _to_float(recon.get("amount"))
    recon["confidence"] = _to_float(recon.get("confidence"))
    recon["line_items"] = [
        {**item, "amount": _to_float(item.get("amount"))}
        for item in recon.get("line_items", [])
    ]
    return recon


def reconcile(invoice_text: str, po: dict[str, Any], llm: Any | None = None) -> dict[str, Any]:
    """Reconcile an invoice with a LangChain chain and return the structured fields."""
    chain = build_chain(llm if llm is not None else default_llm())
    return _normalize(chain.invoke({"invoice_text": invoice_text, "po": json.dumps(po)}))
