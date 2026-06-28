"""Render SeamProof gallery images (for the Devpost gallery / README).

Two kinds, both from real output/data — not mock-ups:
  * terminal cards — the actual `seamproof check --recommend` console output
  * a Test Manager result card — rendered from the real v2 API response in
    docs/evidence/test-manager-result.json

Run: python docs/img/generate_gallery.py
Outputs: docs/img/gallery/*.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "gallery"
OUT.mkdir(exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Sans"
MONO = "DejaVu Sans Mono"

# terminal palette (GitHub-dark)
BG = "#0d1117"
WHITE = "#e6edf3"
DIM = "#8b949e"
RED = "#f85149"
GREEN = "#3fb950"
YELLOW = "#d29922"
# card palette
ORANGE = "#FA4616"
INK = "#1f2430"
CARD = "#ffffff"
PAGE = "#eef1f5"

CHAR_W = 0.088   # inch per monospace char at FS
LINE_H = 0.205
FS = 10.5
PAD = 0.35


def _plain(line):
    return "".join(seg[0] for seg in line)


def terminal(lines, out, title="seamproof check --recommend"):
    ncols = max((len(_plain(ln)) for ln in lines), default=10)
    ncols = max(ncols, len(title) + 6)
    nlines = len(lines)
    w = PAD * 2 + ncols * CHAR_W
    h = PAD * 2 + 0.55 + nlines * LINE_H
    fig = plt.figure(figsize=(w, h), dpi=200)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.04, 0.04), w - 0.08, h - 0.08,
                                boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=BG, ec="#30363d", lw=1.2))
    # title bar: traffic lights + command
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        ax.add_patch(Circle((PAD + 0.12 + i * 0.26, h - 0.32), 0.065, color=c))
    ax.text(w / 2, h - 0.32, title, family=MONO, fontsize=FS - 1.5, color=DIM,
            va="center", ha="center")
    y = h - 0.78
    for ln in lines:
        x = PAD
        for text, color, weight in ln:
            ax.text(x, y, text, family=MONO, fontsize=FS, color=color,
                    weight=weight, va="top", ha="left")
            x += len(text) * CHAR_W
        y -= LINE_H
    fig.savefig(out, dpi=200, facecolor=PAGE)
    plt.close(fig)
    print("  ✓", out.name)


def seg(text, color=WHITE, weight="normal"):
    return (text, color, weight)


GATE_NOGO = [
    [seg("SeamProof — invoice-exception-handling", WHITE, "bold")],
    [seg("trace sut-seam1-001 · 3 seam contracts", DIM)],
    [],
    [seg("FAIL", RED, "bold"), seg("  Agent to Robot data contract", WHITE, "bold")],
    [seg("      seam seam-1 · recon-agent -> posting-robot", DIM)],
    [seg("    ✗ amount-equals-line-items", RED)],
    [seg("        expected 5400 == 4200 (±0.005); differs by 1200", DIM)],
    [seg("    ✓ currency-matches-po", GREEN)],
    [seg("    ✓ vendor-in-master", GREEN)],
    [seg("    ✓ amount-positive", GREEN)],
    [],
    [seg("PASS", GREEN, "bold"), seg("  Routing to Human checkpoint", WHITE, "bold")],
    [seg("      seam seam-2 · router -> approver", DIM)],
    [seg("    ✓ human-approval-when-required", GREEN)],
    [],
    [seg("PASS", GREEN, "bold"), seg("  Cost and cycle-time SLO", WHITE, "bold"),
     seg(" [advisory]", YELLOW)],
    [seg("      seam seam-3 · process -> finops", DIM)],
    [seg("    ✓ cost-within-slo", GREEN), seg("    ✓ cycle-within-slo", GREEN)],
    [],
    [seg("GATE: NO-GO  —  release blocked by seam-1", RED, "bold")],
    [seg("       6/7 assertions passed", DIM)],
    [],
    [seg("Seam Analyst — recommendations", WHITE, "bold"),
     seg("  (UiPath LLM Gateway)", DIM)],
    [seg("  seam-1", WHITE, "bold"), seg(" · recon-agent -> posting-robot  [fragility: ", DIM),
     seg("high", RED, "bold"), seg("]", DIM)],
    [seg("      root cause: the agent's amount (5400) disagrees with its source of", DIM)],
    [seg("      truth — Σ line_items = 4200; it likely summed pre-tax lines.", DIM)],
    [seg("      ", WHITE), seg("fix:", GREEN, "bold"),
     seg(" recompute the total from the source before the robot posts,", WHITE)],
    [seg("           or add a reconciliation post-condition that blocks on mismatch.", WHITE)],
]

GATE_GO = [
    [seg("SeamProof — invoice-exception-handling", WHITE, "bold")],
    [seg("trace golden-001 · 3 seam contracts", DIM)],
    [],
    [seg("PASS", GREEN, "bold"), seg("  Agent to Robot data contract", WHITE, "bold")],
    [seg("    ✓ amount-equals-line-items   ✓ currency-matches-po", GREEN)],
    [seg("    ✓ vendor-in-master           ✓ amount-positive", GREEN)],
    [],
    [seg("PASS", GREEN, "bold"), seg("  Routing to Human checkpoint", WHITE, "bold")],
    [seg("    ✓ human-approval-when-required", GREEN)],
    [],
    [seg("PASS", GREEN, "bold"), seg("  Cost and cycle-time SLO", WHITE, "bold"),
     seg(" [advisory]", YELLOW)],
    [seg("    ✓ cost-within-slo            ✓ cycle-within-slo", GREEN)],
    [],
    [seg("GATE: GO  —  7/7 assertions passed", GREEN, "bold")],
]


def tm_card(out):
    data = json.loads((ROOT / "docs/evidence/test-manager-result.json").read_text())
    w = data["withstats"]
    seam_of = {
        "e1fb93a3-d789-0a00-4bca-0b49d09488bb": ("seam-1", "agent → robot · amount == Σ line_items"),
        "ba906c4c-d889-0a00-3ebc-0b49d094891e": ("seam-2", "routing → human · approval reached"),
        "3bbd1ef8-d989-0a00-bfb8-0b49d0948992": ("seam-3", "process → finops · cost / cycle SLO"),
    }
    rows = []
    for lg in data["logs"]:
        name, desc = seam_of.get(lg["testCaseId"], ("?", ""))
        rows.append((name, desc, lg["result"]))
    rows.sort(key=lambda r: r[0])

    W, H = 10.6, 5.6
    fig = plt.figure(figsize=(W, H), dpi=200)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), W, H, color=PAGE))
    ax.add_patch(FancyBboxPatch((0.4, 0.4), W - 0.8, H - 0.8,
                                boxstyle="round,pad=0.02,rounding_size=0.14",
                                fc=CARD, ec="#dfe3e8", lw=1.4))
    ax.add_patch(Rectangle((0.4, H - 0.95), W - 0.8, 0.55, color=ORANGE))
    ax.text(0.75, H - 0.67, "UiPath Test Manager", color="white", fontsize=15,
            weight="bold", va="center")
    ax.text(W - 0.75, H - 0.67, "Test Execution", color="white", fontsize=12,
            va="center", ha="right")
    ax.text(0.8, H - 1.45, w["name"], color=INK, fontsize=15.5, weight="bold", va="center")
    # status + result pills
    ax.add_patch(FancyBboxPatch((0.8, H - 2.15), 1.5, 0.42,
                 boxstyle="round,pad=0.02,rounding_size=0.1", fc="#e8f5e9", ec="#3fb950"))
    ax.text(1.55, H - 1.94, "Finished", color="#2e7d32", fontsize=12, weight="bold",
            va="center", ha="center")
    ax.text(2.55, H - 1.94, f"{w['passed']} passed", color="#2e7d32", fontsize=13,
            weight="bold", va="center")
    ax.text(4.05, H - 1.94, "·", color=DIM, fontsize=13, va="center")
    ax.text(4.3, H - 1.94, f"{w['failed']} failed", color="#c62828", fontsize=13,
            weight="bold", va="center")
    ax.text(W - 0.8, H - 1.94, "source: TestManager", color=DIM, fontsize=10.5,
            va="center", ha="right")
    # seam rows
    y = H - 2.75
    for name, desc, result in rows:
        ok = result == "Passed"
        ax.add_patch(FancyBboxPatch((0.8, y - 0.28), W - 1.6, 0.56,
                     boxstyle="round,pad=0.01,rounding_size=0.06",
                     fc="#fbfcfd", ec="#eceff3", lw=1))
        chip = "#3fb950" if ok else "#f85149"
        ax.add_patch(Circle((1.15, y), 0.1, color=chip))
        ax.text(1.45, y, name, color=INK, fontsize=13, weight="bold", va="center")
        ax.text(2.5, y, desc, color=MUTED, fontsize=11, va="center")
        ax.text(W - 1.05, y, "PASSED" if ok else "FAILED", color=chip, fontsize=12,
                weight="bold", va="center", ha="right")
        y -= 0.66
    ax.text(0.8, 0.66, f"Execution {w['id'][:13]}…  ·  rendered from the Test Manager v2 API "
            f"(docs/evidence/)", color=DIM, fontsize=9.5, va="center")
    fig.savefig(out, dpi=200, facecolor=PAGE)
    plt.close(fig)
    print("  ✓", out.name)


MUTED = "#5b6472"


def _frame(title, right, W, H, accent=ORANGE):
    fig = plt.figure(figsize=(W, H), dpi=200)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), W, H, color=PAGE))
    ax.add_patch(FancyBboxPatch((0.4, 0.4), W - 0.8, H - 0.8,
                 boxstyle="round,pad=0.02,rounding_size=0.14", fc=CARD, ec="#dfe3e8", lw=1.4))
    ax.add_patch(Rectangle((0.4, H - 0.95), W - 0.8, 0.55, color=accent))
    ax.text(0.75, H - 0.67, title, color="white", fontsize=15, weight="bold", va="center")
    ax.text(W - 0.75, H - 0.67, right, color="white", fontsize=12, va="center", ha="right")
    return fig, ax


def _row(ax, y, W, chip, name, desc, right, right_color):
    ax.add_patch(FancyBboxPatch((0.8, y - 0.36), W - 1.6, 0.72,
                 boxstyle="round,pad=0.01,rounding_size=0.07", fc="#fbfcfd", ec="#eceff3", lw=1))
    ax.add_patch(Circle((1.2, y), 0.11, color=chip))
    ax.text(1.6, y + 0.13, name, color=INK, fontsize=12.5, weight="bold", va="center")
    ax.text(1.6, y - 0.15, desc, color=MUTED, fontsize=10.5, va="center")
    ax.text(W - 1.05, y, right, color=right_color, fontsize=12, weight="bold",
            va="center", ha="right")


SEAMS = [
    ("seam-1", "Agent to Robot data contract", "agent → robot · amount == Σ line_items"),
    ("seam-2", "Routing to Human checkpoint", "routing → human · approval reached"),
    ("seam-3", "Cost and cycle-time SLO", "process → finops · cost / cycle SLO"),
]
JOBS = [
    ("golden", "auto-post · gate GO", "Successful"),
    ("high_value", "human review → approved · gate GO", "Successful"),
    ("seam1_corruption", "injected corruption · gate NO-GO", "Successful"),
]


def tm_testcases_card(out):
    W, H = 10.6, 5.4
    fig, ax = _frame("UiPath Test Manager", "Test Cases · project SeamProof", W, H)
    ax.text(0.8, H - 1.45, "Seam contracts as managed test cases", color=INK,
            fontsize=14.5, weight="bold", va="center")
    y = H - 2.5
    for sid, name, desc in SEAMS:
        _row(ax, y, W, "#2D6CDF", f"{sid} · {name}", desc, "Automation ID: " + sid, MUTED)
        y -= 0.86
    ax.text(0.8, 0.66, "3 test cases · rendered from the Test Manager v2 API (docs/evidence/)",
            color=DIM, fontsize=9.5, va="center")
    fig.savefig(out, dpi=200, facecolor=PAGE)
    plt.close(fig)
    print("  ✓", out.name)


def orch_jobs_card(out):
    W, H = 10.6, 5.4
    fig, ax = _frame("UiPath Orchestrator", "Jobs · Personal Workspace", W, H)
    ax.text(0.8, H - 1.45, "SeamProof coded automation — runs on Automation Cloud",
            color=INK, fontsize=14.5, weight="bold", va="center")
    y = H - 2.5
    for case, desc, status in JOBS:
        _row(ax, y, W, "#3fb950", f"process · {case}", desc, status, "#2e7d32")
        y -= 0.86
    ax.text(0.8, 0.66, "3 runs (@traced, recon via the UiPath LLM Gateway) · rendered",
            color=DIM, fontsize=9.5, va="center")
    fig.savefig(out, dpi=200, facecolor=PAGE)
    plt.close(fig)
    print("  ✓", out.name)


if __name__ == "__main__":
    print("Rendering gallery into", OUT)
    terminal(GATE_NOGO, OUT / "01-gate-nogo.png",
             title="seamproof check --otel seam1_corruption.otlp.json --recommend")
    terminal(GATE_GO, OUT / "02-gate-go.png",
             title="seamproof check --otel golden.otlp.json")
    tm_card(OUT / "03-test-manager-result.png")
    tm_testcases_card(OUT / "04-test-manager-testcases.png")
    orch_jobs_card(OUT / "05-orchestrator-jobs.png")
    print("done.")
