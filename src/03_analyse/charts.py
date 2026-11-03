"""
The two static charts (the maps are in maps.py and docs/map/), drawn and saved to results/figures/:

  quintile_chart(q)  outlets per 100,000 people by wealth quintile, national tiles against the
                     barangays of NCR, Metro Cebu and Metro Davao (quintile_rates.png)
  rate_ratio_chart(m) wealth rate ratios (and presence odds ratios) with 95% intervals for every
                     model variant, one panel per scope (national and the three cities), barangays
                     against tiles in each (rate_ratios.png)

Used by notebooks/01_descriptives.ipynb and notebooks/03_within_cities.ipynb. Each function
returns the saved file, which the notebook shows inline, so readers see the committed chart.
"""
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from analysis_samples import FIGURES

INK, MUTED, RULE, SURFACE = "#292216", "#665B45", "#D9CFBA", "#F8F3E8"
SCOPE_ORDER = ["National", "NCR", "Metro Cebu", "Metro Davao"]
QUINTILE_SERIES = {("National", "tile"): "#2a78d6", ("NCR", "barangay"): "#eb6834",
                   ("Metro Cebu", "barangay"): "#1baf7a", ("Metro Davao", "barangay"): "#8a5cc7"}
QUINTILE_LABEL = {("National", "tile"): "National, RWI tiles", ("NCR", "barangay"): "NCR, barangays",
                  ("Metro Cebu", "barangay"): "Metro Cebu, barangays",
                  ("Metro Davao", "barangay"): "Metro Davao, barangays"}
UNIT_COLOUR = {"barangay": "#eb6834", "tile": "#2a78d6"}
PANEL_TITLE = {"National": "National", "NCR": "Metro Manila (NCR)", "Metro Cebu": "Metro Cebu",
               "Metro Davao": "Metro Davao"}
UNIT_LABEL = {"barangay": "Barangays (main unit in the cities; check nationally)",
              "tile": "RWI tiles (main unit nationally; low-n check in the cities)"}
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
    keys = list(QUINTILE_SERIES)
    with plt.rc_context(STYLE):
        fig, ax = _figure((8, 4))
        width = 0.2
        top = 0
        for i, key in enumerate(keys):
            d = q[(q.scope == key[0]) & (q.unit == key[1])].sort_values("quintile")
            x = d.quintile + (i - (len(keys) - 1) / 2) * (width + 0.01)
            ax.bar(x, d.outlets_per_100k, width=width, color=QUINTILE_SERIES[key], label=QUINTILE_LABEL[key],
                   zorder=2)
            for xi, v in zip(x, d.outlets_per_100k):
                ax.text(xi, v + 0.25, f"{v:.1f}", ha="center", va="bottom", fontsize=6, color=MUTED)
            top = max(top, d.outlets_per_100k.max())
        ax.set_xticks(range(1, 6), ["1\npoorest", "2", "3", "4", "5\nrichest"])
        ax.set_xlabel("Wealth quintile (each a fifth of the scope's people; each city split by its own people)")
        ax.set_ylabel("Outlets per 100,000 people")
        ax.yaxis.grid(True, color=RULE, linewidth=0.6, zorder=0)
        ax.set_ylim(0, top * 1.12)
        ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, fontsize=8)
        ax.set_title("PCSO lotto outlets per person by wealth quintile", loc="left", fontsize=11,
                     fontweight="bold", pad=24)
        _tidy(ax)
        fig.tight_layout()
        fig.savefig(FIGURES / "quintile_rates.png")
    return FIGURES / "quintile_rates.png"


def rate_ratio_chart(m):
    """m: the models table (sensitivity rows are left out). A missing mark is a model that was
    not estimable or not run for that scope and unit."""
    m = m[~m.model.str.startswith("count, sensitivity")]
    rows = [r for r in ROWS if ((m.model == r[0]) & (m.variant == r[1])).any()]
    scopes = [s for s in SCOPE_ORDER if (m.scope == s).any()]
    lo = min(0.5, m.ci_low.min() * 0.9)
    hi = max(4, m.ci_high.max() * 1.1)
    ticks = [t for t in (0.25, 0.5, 1, 2, 4, 8, 16) if lo <= t <= hi]
    with plt.rc_context(STYLE):
        fig = Figure(figsize=(2.35 * len(scopes) + 2.4, 0.42 * len(rows) + 1.9), dpi=200)
        FigureCanvasAgg(fig)
        axes = fig.subplots(1, len(scopes), sharey=True)
        for ax, scope in zip(axes, scopes):
            for j, (model, variant) in enumerate(rows):
                y = len(rows) - 1 - j
                for k, unit in enumerate(("barangay", "tile")):
                    d = m[(m.model == model) & (m.variant == variant) & (m.scope == scope) & (m.unit == unit)]
                    if d.empty:
                        continue
                    r = d.iloc[0]
                    yy = y + (0.14 if unit == "barangay" else -0.14)
                    ax.plot([r.ci_low, r.ci_high], [yy] * 2, color=UNIT_COLOUR[unit], linewidth=2,
                            solid_capstyle="round")
                    ax.plot(r.wealth_ratio, yy, "o", color=UNIT_COLOUR[unit], markersize=4.5,
                            markeredgecolor=SURFACE, markeredgewidth=1)
            ax.axvline(1, color=INK, linewidth=0.8)
            ax.set_xscale("log")
            ax.set_xlim(lo, hi)
            ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
            ax.minorticks_off()
            ax.xaxis.grid(True, color=RULE, linewidth=0.6)
            ax.set_title(PANEL_TITLE[scope], loc="left", fontsize=9.5, fontweight="bold")
            _tidy(ax)
        axes[0].set_yticks(range(len(rows)), [ROW_LABEL[r] for r in rows][::-1])
        fig.suptitle("Wealth ratio by model variant, with 95% intervals", x=0.01, ha="left", fontsize=11,
                     fontweight="bold")
        fig.supxlabel("Wealth ratio per 1 national SD of RWI (log scale); above 1: more outlets per person "
                      "in richer places", fontsize=8.5, color=INK)
        handles = [plt.Line2D([], [], color=UNIT_COLOUR[u], marker="o", linewidth=2, label=UNIT_LABEL[u])
                   for u in ("barangay", "tile")]
        fig.legend(handles=handles, frameon=False, loc="upper right", ncol=2, fontsize=8,
                   bbox_to_anchor=(0.995, 1.0))
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        fig.savefig(FIGURES / "rate_ratios.png")
    return FIGURES / "rate_ratios.png"
