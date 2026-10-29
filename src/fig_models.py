#!/usr/bin/env python3
"""Rate ratios by wealth quintile, national and in the three cities. Run after cities.py."""
import json

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator  # noqa: E402

from common import BG, DERIVED, FIGURES, INK, MUTED, RULE  # noqa: E402

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": INK, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": RULE, "axes.linewidth": 1.0,
})
SAVE = dict(dpi=170, bbox_inches="tight", metadata={"Software": None})
# Two-series pair checked with the dataviz palette validator against the cream surface
RUST, BLUE = "#A8461E", "#2A6CA8"

nat = json.load(open(DERIVED / "national_models.json"))["models"]
cit = json.load(open(DERIVED / "cities_models.json"))["models"]


def series(model):
    q = model["quintiles"]
    rr = [q[f"q{k}"]["rr"] for k in range(1, 5)] + [1.0]
    lo = [q[f"q{k}"]["lo"] for k in range(1, 5)] + [1.0]
    hi = [q[f"q{k}"]["hi"] for k in range(1, 5)] + [1.0]
    return np.array(rr), np.array(lo), np.array(hi)


def draw(ax, x, model, color, marker, label):
    rr, lo, hi = series(model)
    ax.vlines(x[:4], lo[:4], hi[:4], color=color, lw=2)
    ax.plot(x, rr, ls="none", marker=marker, ms=8, color=color, mec=BG, mew=1.5, label=label)


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
x = np.arange(1, 6)
draw(ax1, x - 0.12, nat["no_commerce"], RUST, "o", "Population, urbanity, province")
draw(ax1, x + 0.12, nat["full"], BLUE, "s", "... plus commerce controls")
ax1.set_title("All barangays: commerce controls flatten the gradient", fontsize=12.5, loc="left", pad=8)
ax1.legend(frameon=False, fontsize=9, loc="lower right")
draw(ax2, x, cit["share_osm"], BLUE, "s", None)
ax2.set_title("Three cities: lotto share of mapped retail", fontsize=12.5, loc="left", pad=8)
for ax, xlabel in [(ax1, "National wealth quintile  (1 = poorest, 5 = richest)"),
                   (ax2, "Within-city wealth quintile  (1 = poorest, 5 = richest)")]:
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(FixedLocator([0.01, 0.03, 0.1, 0.3, 1, 3, 10]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.axhline(1, color=MUTED, lw=1, ls=(0, (4, 3)))
    ax.set_xticks(x)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=RULE, lw=0.6, alpha=0.6)
    ax.set_axisbelow(True)
ax1.set_ylabel("Rate ratio against the richest quintile (log scale)", fontsize=10)
fig.tight_layout()
fig.savefig(FIGURES / "fig_rate_ratios.png", **SAVE)
print("wrote figures/fig_rate_ratios.png")
