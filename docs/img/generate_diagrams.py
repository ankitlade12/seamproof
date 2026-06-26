"""Generate SeamProof's diagram PNGs (architecture + the three seams).

Run: python docs/img/generate_diagrams.py
Outputs: docs/img/architecture.png, docs/img/seams.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent
plt.rcParams["font.family"] = "DejaVu Sans"

ORANGE = "#FA4616"   # UiPath accent
INK = "#1f2430"
MUTED = "#5b6472"
GREEN = "#2BA84A"
RED = "#E5484D"
AGENT = "#2D6CDF"
ROUTER = "#8A6D00"
HUMAN = "#2BA84A"
ROBOT = "#7A3FF2"


def box(ax, x, y, w, h, text, *, ec=INK, fc="white", tc=INK, fs=11, bold=False, round=0.06):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={round}",
            linewidth=1.8, edgecolor=ec, facecolor=fc, mutation_aspect=1,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, x1, y1, x2, y2, *, color=ORANGE, lw=2.2, label=None, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16,
                                 linewidth=lw, color=color, linestyle=ls,
                                 shrinkA=2, shrinkB=2))
    if label:
        if abs(x2 - x1) < 0.3:   # vertical arrow -> label to the right of the line
            ax.text(x1 + 0.2, (y1 + y2) / 2, label, ha="left", va="center",
                    fontsize=9, color=MUTED, style="italic")
        else:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, ha="center", va="bottom",
                    fontsize=9, color=MUTED, style="italic")


def architecture():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 12); ax.set_ylim(0, 7.2); ax.axis("off")
    ax.text(0.2, 6.9, "SeamProof", fontsize=22, fontweight="bold", color=ORANGE)
    ax.text(0.2, 6.55, "Test the seams of an agentic process, not just the actors.",
            fontsize=11, color=MUTED)

    # System under test container
    ax.add_patch(FancyBboxPatch((0.3, 4.7), 11.4, 1.45, boxstyle="round,pad=0.02,rounding_size=0.08",
                                linewidth=1.4, edgecolor="#c8cdd6", facecolor="#f6f7f9"))
    ax.text(0.55, 5.95, "System under test  ·  UiPath coded automation / Maestro",
            fontsize=10, color=MUTED, fontweight="bold")
    actors = [
        (0.7, "Recon Agent", "LLM Gateway /\nLangChain", AGENT),
        (3.55, "Router", "routing\ndecision", ROUTER),
        (6.4, "Human", "Action Center\napproval", HUMAN),
        (9.25, "Posting Robot", "RPA → ERP", ROBOT),
    ]
    yb = 4.95
    for x, title, sub, c in actors:
        box(ax, x, yb, 2.05, 0.85, f"{title}\n{sub}", ec=c, fc="white", fs=10.5, bold=True)
    for i in range(3):
        arrow(ax, actors[i][0] + 2.05, yb + 0.42, actors[i + 1][0], yb + 0.42)

    # seam ticks across the handoff arrows
    for sx, sl in ((2.93, "seam-1"), (5.78, "seam-2")):
        ax.plot([sx, sx], [yb + 0.18, yb + 0.66], color=ORANGE, lw=2.6, solid_capstyle="round")
        ax.text(sx, yb - 0.02, sl, fontsize=8.5, color=ORANGE, fontweight="bold", ha="center", va="top")

    arrow(ax, 6.0, 4.7, 6.0, 4.05, label="OpenTelemetry trace")

    # SeamProof engine
    ax.add_patch(FancyBboxPatch((0.3, 2.35), 11.4, 1.55, boxstyle="round,pad=0.02,rounding_size=0.08",
                                linewidth=2.0, edgecolor=ORANGE, facecolor="#fff6f3"))
    ax.text(0.55, 3.68, "SeamProof", fontsize=11, color=ORANGE, fontweight="bold")
    box(ax, 0.9, 2.6, 2.6, 0.85, "Run trace\n(events + context)", ec=MUTED, fs=10)
    box(ax, 4.0, 2.6, 3.0, 0.85, "Seam contracts\nproperty assertions", ec=MUTED, fs=10)
    box(ax, 7.6, 2.6, 3.4, 0.85, "Release gate\nblocking / advisory", ec=ORANGE, fs=10, bold=True)
    arrow(ax, 3.5, 3.02, 4.0, 3.02)
    arrow(ax, 7.0, 3.02, 7.6, 3.02)

    arrow(ax, 6.0, 2.35, 6.0, 1.7, label="go / no-go")

    # outputs
    box(ax, 1.6, 0.7, 2.9, 0.9, "Test Manager\nresult per seam", ec=AGENT, fs=10.5, bold=True)
    box(ax, 5.05, 0.7, 2.0, 0.9, "CI / JUnit\nexit code", ec=MUTED, fs=10.5)
    box(ax, 7.6, 0.95, 1.6, 0.55, "GATE: GO", ec=GREEN, tc=GREEN, fs=11, bold=True)
    box(ax, 9.4, 0.95, 1.9, 0.55, "GATE: NO‑GO", ec=RED, tc=RED, fs=11, bold=True)
    arrow(ax, 4.5, 1.15, 5.05, 1.15, color=MUTED, lw=1.6)

    fig.savefig(OUT / "architecture.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def seams():
    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.set_xlim(0, 11); ax.set_ylim(0, 5.6); ax.axis("off")
    ax.text(0.2, 5.2, "The three seams", fontsize=20, fontweight="bold", color=INK)
    ax.text(0.2, 4.85, "A seam contract = the properties the receiving actor depends on.",
            fontsize=11, color=MUTED)

    rows = [
        (3.55, "Recon Agent", "Posting Robot", "Seam 1 — data contract",
         "amount == Σ line items, currency == PO, vendor approved", "blocking", AGENT, ROBOT),
        (2.15, "Router", "Human", "Seam 2 — checkpoint",
         "when policy requires a human, an approval fires before the robot posts", "blocking", ROUTER, HUMAN),
        (0.75, "Process", "FinOps", "Seam 3 — cost / cycle SLO",
         "cost-per-run and cycle time stay within the SLO", "advisory", MUTED, MUTED),
    ]
    for y, a, b, title, desc, sev, ca, cb in rows:
        box(ax, 0.4, y, 1.9, 0.9, a, ec=ca, fs=10.5, bold=True)
        box(ax, 3.1, y, 1.9, 0.9, b, ec=cb, fs=10.5, bold=True)
        arrow(ax, 2.3, y + 0.45, 3.1, y + 0.45)
        ax.plot([2.7, 2.7], [y + 0.27, y + 0.63], color=ORANGE, lw=3, solid_capstyle="round")
        ax.text(2.7, y + 0.95, "seam", fontsize=8.5, color=ORANGE, ha="center", fontweight="bold")
        sev_c = RED if sev == "blocking" else "#B7791F"
        ax.text(5.35, y + 0.62, title, fontsize=12, color=INK, fontweight="bold")
        ax.text(5.35, y + 0.30, desc, fontsize=10, color=MUTED)
        ax.text(5.35, y + 0.02, sev, fontsize=9, color=sev_c, fontweight="bold")

    fig.savefig(OUT / "seams.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    architecture()
    seams()
    print("wrote architecture.png and seams.png")
