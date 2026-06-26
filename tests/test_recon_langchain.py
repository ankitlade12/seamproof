"""Integration test for the external LangChain recon agent.

Uses the **real** UiPath LLM Gateway (`UiPathChat`) — no fake model. It is skipped
unless `uipath-langchain` is installed *and* UiPath credentials are present (run
`uipath auth`), so it stays out of CI but exercises the real model when you have a
session. The model is non-deterministic, so it asserts the output *shape* (and that
amounts are normalised to floats), not exact values.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("uipath_langchain")

ROOT = Path(__file__).resolve().parent.parent
RECON_LC = ROOT / "sut" / "automation" / "recon_langchain.py"

_HAS_CREDS = bool(os.environ.get("UIPATH_URL") and os.environ.get("UIPATH_ACCESS_TOKEN"))


def _load_recon_langchain():
    spec = importlib.util.spec_from_file_location("recon_langchain_mod", RECON_LC)
    module = importlib.util.module_from_spec(spec)
    sys.modules["recon_langchain_mod"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not _HAS_CREDS, reason="needs UiPath credentials (uipath auth) for the real LLM Gateway")
def test_langchain_recon_real_gateway():
    rl = _load_recon_langchain()
    recon = rl.reconcile(
        "INVOICE\nVendor: Acme Supplies (V-1042)\nCurrency: USD\n"
        "Line items:\n  A1 Widget .. 1,200.00\n  B2 Gadget .. 3,000.00\nTOTAL DUE: USD 5,400.00",
        {"number": "PO-88231", "currency": "USD", "vendor_id": "V-1042", "amount": 4200.0},
    )
    assert recon["vendor_id"]
    assert isinstance(recon["amount"], float)  # normalised from the model's "5,400.00"
    assert recon["line_items"]
    assert all(isinstance(item["amount"], float) for item in recon["line_items"])
