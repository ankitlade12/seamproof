# Demo recording kit — record it today, offline

Companion to [demo-script.md](demo-script.md). That file is *what to say*; this is *how
to record it without anything breaking on camera*. **Verified:** all core beats run
**fully offline** (the gate and the Seam Analyst never touch the cloud), so you don't
need the tenant up to record. The "it's real on UiPath" proof is shown from artifacts
you already have committed.

## One-time setup (before you hit record)

```bash
cd /Users/ankithemantlade/Desktop/Hackathon/uipath
export PYTHONPATH=src SEAMPROOF_FORCE_COLOR=1     # color shows up in the recording

# pre-generate the traces so there's no waiting on camera
cd sut/automation
python3 main.py golden            golden.otlp.json
python3 main.py seam1_corruption  seam1_corruption.otlp.json
python3 main.py seam2_near_ceiling seam2_near_ceiling.otlp.json
cd ../..
```

- **Terminal:** ~18pt font, ~100 columns, clean prompt (hide your username if you like).
- **Open in browser tabs (for the "real on UiPath" beats):** `docs/img/architecture.png`,
  your **Orchestrator → Jobs** page (the 3 runs), and the committed
  [evidence doc](evidence/test-manager-evidence.md).
- **Record each beat as a separate clip**, then stitch (QuickTime + iMovie/CapCut). If
  you fluff a line, just re-record that one beat — no need for a perfect single take.

## The reliable offline run (beats 1–5, 8 — 100% no cloud)

Run these from the repo root with `PYTHONPATH=src` set. Each line: **TYPE → SCREEN → SAY**.

**Beat 1 · 0:00–0:30 · Problem** — *(no command; show `architecture.png`)*
> SAY: "Agents, robots, and humans run in one flow, and we test each in isolation. The
> incidents come from the **seams between them**. SeamProof is the release gate for the
> handoffs."

**Beat 2 · 0:30–1:10 · A clean run (GO)**
```bash
python3 -m seamproof check -c contracts --otel sut/automation/golden.otlp.json
```
- SCREEN: `GATE: GO — 7/7 assertions passed`
> SAY: "A real UiPath coded automation — agent, router, human, robot — emits an OTEL
> trace. SeamProof gates a clean run: **GO**."

**Beat 3 · 1:10–2:10 · Break Seam 1 (the money shot)**
```bash
python3 -m seamproof check -c contracts --otel sut/automation/seam1_corruption.otlp.json
```
- SCREEN: `GATE: NO-GO — release blocked by seam-1` · `expected 5400 == 4200, differs by 1200`
> SAY: "The agent extracts **$5,400** — valid JSON, but line items sum to $4,200. The
> robot would post a $1,200 overpayment. The seam asserts `amount == sum(line_items)`:
> **NO-GO, blocked by seam-1.**" *(Hold the red NO-GO on screen.)*

**Beat 4 · 2:10–2:55 · The Seam Analyst recommends the fix ⭐**
```bash
python3 -m seamproof check -c contracts --otel sut/automation/seam1_corruption.otlp.json --recommend
```
- SCREEN: `Seam Analyst — recommendations` · root cause + **fix** + `fragility: high`
> SAY: "The gate doesn't stop at *no*. `--recommend` runs the **Seam Analyst** — an agent
> on the UiPath LLM Gateway — which returns the **root cause** and a **concrete fix**, and
> rates the seam **high fragility**. The tester is itself an agent." *(This is the
> differentiator — keep it on screen.)*

**Beat 5 · 2:55–3:35 · Break Seam 2 (skipped checkpoint)**
```bash
python3 -m seamproof check -c contracts --otel sut/automation/seam2_near_ceiling.otlp.json
```
- SCREEN: `GATE: NO-GO — release blocked by seam-2`
> SAY: "A $9,950 invoice auto-posts **around** the required human approval. The seam
> asserts an approval must precede the post — it's missing. **NO-GO, blocked by seam-2.**"

**Beat 8 · 4:45–5:00 · Close** — *(no command)*
> SAY: "SeamProof is the QA layer for composite agentic processes — the connective
> tissue. The seams, the tests, and the Seam Analyst were authored with a coding agent
> through UiPath for Coding Agents. **Test the seams, not just the actors.**"

## The "real on UiPath" beats (6 & 7) — two ways

These are the only cloud-touching beats. Pick whichever is safe on recording day:

**Beat 6 · 3:35–4:10 · Agent quality + cross-platform**
- *Live (tenant up):* `uipath eval extract evaluations/eval-sets/recon.json --no-report`
  (scores 1.0) and `uipath run process '{"case":"seam1_corruption","use_langchain":true}'`.
- *Offline-safe:* show the eval set file and `recon_langchain.py` on screen and say "the
  agent scores 1.0 on `uipath eval`, and the recon agent also runs as an external
  LangChain agent through the UiPath Gateway — same gate."

**Beat 7 · 4:10–4:45 · The gate in Test Manager**
- *Live (you have view access):* open the **SeamProof** project → the **Finished**
  execution → seam-1 the failure (2 passed · 1 failed).
- *Offline-safe:* show the committed [evidence doc](evidence/test-manager-evidence.md)
  (Finished execution, per-seam results, real execution id) and your Orchestrator Jobs
  page. Say "this published a real Finished execution — here's the captured result."

## If you only have 10 minutes

Record **beats 1–5 + 8 offline** (that's the whole core arc and the money shot + the
agent fix — ~3:35 of the 5:00). Then screen-capture **Orchestrator Jobs** and the
**evidence doc** as beats 6–7 B-roll and narrate over them. Done.
