#!/usr/bin/env python3
"""Charts in the Muted Archive palette. Run after analysis.py and robustness.py."""
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import ACCENT, BG, DERIVED, FIGURES, INK, MUTED, RULE, WEALTH, WORK  # noqa: E402

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": INK, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": RULE, "axes.linewidth": 1.0,
})
SAVE = dict(dpi=170, bbox_inches="tight", metadata={"Software": None})

dec = pd.read_csv(DERIVED / "decile_table.csv")
ncrq = pd.read_csv(DERIVED / "ncr_quintiles.csv")
cells = pd.read_csv(WORK / "analysis_cells.csv")

# --- Figure 1: national decile gradient + NCR quintiles side by side ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1.35, 1]})

x = dec["decile"].values
ax1.bar(x, dec["outlets_per_100k"], color=[WEALTH(i / (len(x) - 1)) for i in range(len(x))],
        edgecolor=INK, linewidth=0.6, width=0.78)
ax1.set_xticks(x)
ax1.set_xlabel("Neighbourhood wealth decile  (1 = poorest ... 10 = richest)", fontsize=10)
ax1.set_ylabel("Lotto outlets per 100,000 people", fontsize=10)
ax1.set_title("National: mapped outlets rise with wealth", fontsize=12.5, color=INK, pad=8, loc="left")
for i, v in zip(x, dec["outlets_per_100k"]):
    ax1.text(i, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=7.5, color=MUTED)
ax1.spines[["top", "right"]].set_visible(False)
ax1.margins(y=0.14)

xq = ncrq["quintile"].values
ax2.bar(xq, ncrq["outlets_per_100k"], color=[WEALTH(i / 4) for i in range(5)],
        edgecolor=INK, linewidth=0.6, width=0.72)
ax2.set_xticks(xq)
ax2.set_xlabel("Wealth quintile within Metro Manila", fontsize=10)
ax2.set_title("Within Metro Manila: no clear gradient", fontsize=12.5, color=INK, pad=8, loc="left")
for i, v in zip(xq, ncrq["outlets_per_100k"]):
    ax2.text(i, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=7.5, color=MUTED)
ax2.spines[["top", "right"]].set_visible(False)
ax2.margins(y=0.16)
ax2.axhline(ncrq["outlets_per_100k"].mean(), ls=(0, (4, 3)), lw=1, color=ACCENT, alpha=0.8)

fig.tight_layout()
fig.savefig(FIGURES / "fig_gradient.png", **SAVE)
print("wrote figures/fig_gradient.png")

# --- Figure 2: wealth where people live vs where outlets are ---
fig2, ax = plt.subplots(figsize=(7.6, 3.6))
allc = cells[cells["pop"] > 0]
bins = np.linspace(-2, 2.4, 40)
ax.hist(allc["rwi"], bins=bins, weights=allc["pop"], density=True, color=RULE,
        alpha=0.85, label="Where people live (population-weighted)", edgecolor="none")
ax.hist(allc["rwi"], bins=bins, weights=allc["n_outlets"], density=True, histtype="step",
        color=ACCENT, linewidth=2.2, label="Where mapped outlets are (outlet-weighted)")
ax.set_xlabel("Relative Wealth Index of neighbourhood  (lower = poorer, higher = richer)", fontsize=10)
ax.set_ylabel("Density", fontsize=10)
ax.set_title("Mapped outlets sit at higher wealth than people do", fontsize=12.5, loc="left", pad=8)
ax.legend(frameon=False, fontsize=9, loc="upper left")
ax.spines[["top", "right"]].set_visible(False)
fig2.tight_layout()
fig2.savefig(FIGURES / "fig_distribution.png", **SAVE)
print("wrote figures/fig_distribution.png")
