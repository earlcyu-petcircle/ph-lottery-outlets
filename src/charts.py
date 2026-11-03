#!/usr/bin/env python3
"""
Two static charts from the step 3 tables (the maps are in docs/map/):

  results/figures/quintile_rates.png  outlets per 100,000 people by wealth quintile,
                                      national tiles against NCR barangays
  results/figures/rate_ratios.png     wealth rate ratios (and presence odds ratios) with 95%
                                      intervals for every model variant, national against NCR

Run after models.py:  python src/charts.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from analysis_data import FIGURES, TABLES  # noqa: E402

INK, MUTED, RULE, SURFACE = "#292216", "#665B45", "#D9CFBA", "#F8F3E8"
SERIES = {("National", "tile"): "#2a78d6", ("NCR", "barangay"): "#eb6834",
          ("National", "barangay"): "#1baf7a", ("NCR", "tile"): "#eda100"}
LABEL = {("National", "tile"): "National, RWI tiles", ("NCR", "barangay"): "NCR, barangays",
         ("National", "barangay"): "National, barangays (check)", ("NCR", "tile"): "NCR, RWI tiles (low n)"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})


def tidy(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


# --- Quintile rates --------------------------------------------------------------------
q = pd.read_csv(TABLES / "quintile_rates.csv")
q = q[q.quintile != "All"].assign(quintile=lambda d: d.quintile.astype(int))
fig, ax = plt.subplots(figsize=(7, 3.8), dpi=200)
width = 0.38
for i, key in enumerate((("National", "tile"), ("NCR", "barangay"))):
    d = q[(q.scope == key[0]) & (q.unit == key[1])].sort_values("quintile")
    x = d.quintile + (i - 0.5) * (width + 0.02)
    ax.bar(x, d.outlets_per_100k, width=width, color=SERIES[key], label=LABEL[key], zorder=2)
    for xi, v in zip(x, d.outlets_per_100k):
        ax.text(xi, v + 0.25, f"{v:.1f}", ha="center", va="bottom", fontsize=7.5, color=MUTED)
ax.set_xticks(range(1, 6), ["1\npoorest", "2", "3", "4", "5\nrichest"])
ax.set_xlabel("Wealth quintile (each a fifth of the scope's people; NCR split by its own people)")
ax.set_ylabel("Outlets per 100,000 people")
ax.yaxis.grid(True, color=RULE, linewidth=0.6, zorder=0)
ax.set_ylim(0, q.outlets_per_100k.max() * 1.12)
ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
ax.set_title("PCSO lotto outlets per person by wealth quintile", loc="left", fontsize=11, fontweight="bold",
             pad=24)
tidy(ax)
fig.tight_layout()
fig.savefig(FIGURES / "quintile_rates.png")
plt.close(fig)

# --- Rate-ratio forest plot ------------------------------------------------------------
m = pd.read_csv(TABLES / "models.csv")
m = m[~m.model.str.startswith("count, sensitivity")]
ROWS = [("count", "wealth only"), ("count", "+ urban share"), ("count", "+ shops"), ("count", "+ shops and roads"),
        ("count, spatial refit", "+ urban share"), ("count, spatial refit", "+ shops"),
        ("presence", "+ urban share"), ("presence", "+ shops")]
ROW_LABEL = {("count", "wealth only"): "Count: wealth only", ("count", "+ urban share"): "Count: + urban share",
             ("count", "+ shops"): "Count: + shops", ("count", "+ shops and roads"): "Count: + shops and roads",
             ("count, spatial refit", "+ urban share"): "Spatial refit: + urban share",
             ("count, spatial refit", "+ shops"): "Spatial refit: + shops",
             ("presence", "+ urban share"): "Presence (odds ratio): + urban share",
             ("presence", "+ shops"): "Presence (odds ratio): + shops"}
rows = [r for r in ROWS if ((m.model == r[0]) & (m.variant == r[1])).any()]
keys = list(SERIES)
fig, ax = plt.subplots(figsize=(8, 0.55 * len(rows) + 1.8), dpi=200)
offset = {k: (i - 1.5) * 0.17 for i, k in enumerate(keys)}
for j, (model, variant) in enumerate(rows):
    y = len(rows) - 1 - j
    for k in keys:
        d = m[(m.model == model) & (m.variant == variant) & (m.scope == k[0]) & (m.unit == k[1])]
        if d.empty:
            continue
        r = d.iloc[0]
        ax.plot([r.ci_low, r.ci_high], [y + offset[k]] * 2, color=SERIES[k], linewidth=2, solid_capstyle="round")
        ax.plot(r.wealth_ratio, y + offset[k], "o", color=SERIES[k], markersize=5,
                markeredgecolor=SURFACE, markeredgewidth=1, label=LABEL[k] if j == 0 else None)
ax.axvline(1, color=INK, linewidth=0.8)
ax.set_xscale("log")
ax.set_xlim(0.6, 3.2)
ticks = [0.75, 1, 1.5, 2, 3]
ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
ax.minorticks_off()
ax.set_yticks(range(len(rows)), [ROW_LABEL[r] for r in rows][::-1])
ax.xaxis.grid(True, color=RULE, linewidth=0.6)
ax.set_xlabel("Wealth ratio per 1 national SD of RWI (log scale)\nabove 1: more outlets per person in richer places")
ax.set_title("Wealth ratio by model variant, with 95% intervals", loc="left", fontsize=11, fontweight="bold")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.4, -0.2), ncol=2, fontsize=8)
tidy(ax)
fig.tight_layout()
fig.savefig(FIGURES / "rate_ratios.png")
plt.close(fig)
print("wrote", FIGURES / "quintile_rates.png", "and", FIGURES / "rate_ratios.png")
