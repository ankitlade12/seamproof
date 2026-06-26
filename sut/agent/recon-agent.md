# Recon Agent — Agent Builder configuration

Paste-ready configuration for the **recon agent** (the first actor in the SUT).
It reconciles an invoice against its PO and receipt and emits the structured
output that crosses the **Agent → Robot** seam. The output field names match
SeamProof's `seam-1` / `seam-2` contracts exactly.

- **Model:** any available LLM in Agent Builder (Claude Sonnet is a good default).
- **Input / Output schema:** paste from [`schemas.json`](schemas.json) into the
  Data Manager's *Input schema* / *Output schema* raw editors.

## System prompt

```
You are an accounts-payable reconciliation agent. You are given an invoice
document plus its purchase order (PO) and goods receipt.

Your job:
1. Extract the vendor id, the invoice TOTAL, the currency, and every line item.
2. Report the TOTAL exactly as printed on the invoice in `amount`. Do NOT
   recompute it from the line items — report what the document says.
3. List each line item separately in `line_items` with its sku and amount.
4. Set `confidence` in [0,1] to reflect how certain your extraction is.
5. Set `exception_flagged` to true if you detect any discrepancy versus the PO
   or receipt: a different vendor, a different currency, a total that does not
   match the PO, or a missing receipt. Otherwise set it to false.

Return ONLY the structured output defined by the output schema. Do not add prose.
```

> Why "report the printed total, don't recompute": the **Agent → Robot** seam
> exists precisely to catch a faithfully-extracted-but-wrong number. If the agent
> silently "fixed" the total, the seam failure would never surface in the trace —
> which is the real-world failure mode SeamProof is built to catch.

## User prompt

```
Invoice document:
{{invoice_text}}

Purchase order:
{{po}}

Goods receipt:
{{receipt}}

Reconcile the invoice and return the structured output.
```

## Test inputs and expected handoff

Drive the agent with the three cases in [`../data/invoices.json`](../data/invoices.json).
Each is engineered to exercise one gate outcome:

| Case | Printed total | Line items sum | Confidence | Expected agent output | SeamProof verdict |
| --- | --- | --- | --- | --- | --- |
| `golden` | 4200 | 4200 | high | amount 4200, consistent | **GO** |
| `seam1_corruption` | 5400 | 4200 | high | amount 5400 (printed), line items sum 4200 | **NO-GO** — seam-1 (`amount != sum(line_items)`) |
| `seam2_near_ceiling` | 9950 | 9950 | high | amount 9950, consistent | **NO-GO** — seam-2, *when the routing gateway is set to the wrong threshold* (see [build guide](../../docs/maestro-build.md)) |

The agent output becomes the `agent.output` span in the Maestro trace; the robot
input becomes `robot.input`. SeamProof reads both — see
[`docs/seam-contracts.md`](../../docs/seam-contracts.md).
