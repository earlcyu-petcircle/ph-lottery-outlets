"""
The two static charts (the maps are in docs/map/), drawn and saved to results/figures/:

  quintile_chart(q)  outlets per 100,000 people by wealth quintile, national tiles against
                     NCR barangays (quintile_rates.png)
  rate_ratio_chart(m) wealth rate ratios (and presence odds ratios) with 95% intervals for every
                     model variant, national against NCR (rate_ratios.png)

Used by notebooks/01_descriptives.ipynb and notebooks/03_ncr_zoom_in.ipynb. Each function
returns the saved file, which the notebook shows inline, so readers see the committed chart.
"""
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from analysis_samples import FIGURES

INK, MUTED, RULE, SURFACE = "#292216", "#665B45", "#D9CFBA", "#F8F3E8"
SERIES = {("National", "tile"): "#2a78d6", ("NCR", "barangay"): "#eb6834",
          ("National", "barangay"): "#1baf7a", ("NCR", "tile"): "#eda100"}
LABEL = {("National", "tile"): "National, RWI tiles", ("NCR", "barangay"): "NCR, barangays",
         ("National", "barangay"): "National, barangays (check)", ("NCR", "tile"): "NCR, RWI tiles (low n)"}
STYLE = {"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED,
         "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
         "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE}
ROWS = [("count", "wealth only"), ("count", "+ urban share"), ("count", "+ shops"), ("count", "+ shops and roads"),
        ("count, spatial refit", "+ urban share"), ("count, spatial refit", "+ shops"),
        ("presence", "+ urban share"), ("presence", "+ shops")]
ROW_LABEL = {("count", "wealth only"): "Count: wealth only", ("count", "+ urban share"): "Count: + urban share",
             ("count", "+ shops"): "Count: + shops", ("count", "+ shops and roads"): "Count: + shops and roads",
             ("count, spatial refit", "+ urban share"): "Spatial refit: + urban share",
             ("count, spatial refit", "+ shops"): "Spatial refit: + shops",
             ("presence", "+ urban share"): "Presence (odds ratio): + urban share",
             ("presence", "+ shops"): "Presence (odds ratio): + shops"}


def _figure(figsize):
    """A figure on its own Agg canvas, outside pyplot, so a notebook does not also draw it."""
    fig = Figure(figsize=figsize, dpi=200)
    FigureCanvasAgg(fig)
    return fig, fig.add_subplot()


def _tidy(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def quintile_chart(q):
    """q: the quintile_rates table."""
    q = q[q.quintile != "All"].assign(quintile=lambda d: d.quintile.astype(int))
    with plt.rc_context(STYLE):
        fig, ax = _figure((7, 3.8))
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
        ax.set_title("PCSO lotto outlets per person by wealth quintile", loc="left", fontsize=11,
                     fontweight="bold", pad=24)
        _tidy(ax)
        fig.tight_layout()
        fig.savefig(FIGURES / "quintile_rates.png")
    return FIGURES / "quintile_rates.png"


def rate_ratio_chart(m):
    """m: the models table (sensitivity rows are left out)."""
    m = m[~m.model.str.startswith("count, sensitivity")]
    rows = [r for r in ROWS if ((m.model == r[0]) & (m.variant == r[1])).any()]
    keys = list(SERIES)
    with plt.rc_context(STYLE):
        fig, ax = _figure((8, 0.55 * len(rows) + 1.8))
        offset = {k: (i - 1.5) * 0.17 for i, k in enumerate(keys)}
        for j, (model, variant) in enumerate(rows):
            y = len(rows) - 1 - j
            for k in keys:
                d = m[(m.model == model) & (m.variant == variant) & (m.scope == k[0]) & (m.unit == k[1])]
                if d.empty:
                    continue
                r = d.iloc[0]
                ax.plot([r.ci_low, r.ci_high], [y + offset[k]] * 2, color=SERIES[k], linewidth=2,
                        solid_capstyle="round")
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
        ax.set_xlabel("Wealth ratio per 1 national SD of RWI (log scale)\n"
                      "above 1: more outlets per person in richer places")
        ax.set_title("Wealth ratio by model variant, with 95% intervals", loc="left", fontsize=11, fontweight="bold")
        ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.4, -0.2), ncol=2, fontsize=8)
        _tidy(ax)
        fig.tight_layout()
        fig.savefig(FIGURES / "rate_ratios.png")
    return FIGURES / "rate_ratios.png"
