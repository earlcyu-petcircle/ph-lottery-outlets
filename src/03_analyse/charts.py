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

import atlas
from analysis_samples import FIGURES

SCOPE_ORDER = ["National", "NCR", "Metro Cebu", "Metro Davao"]
QUINTILE_PANELS = [("National", "tile", "Philippines", "2.4 km tiles"),
                   ("NCR", "barangay", "Metro Manila", "barangays"),
                   ("Metro Cebu", "barangay", "Metro Cebu", "barangays"),
                   ("Metro Davao", "barangay", "Metro Davao", "barangays")]
# Barangays in cobalt (the main unit in the cities), tiles in ink (the main unit nationally)
UNIT_MARK = {"barangay": {"color": atlas.ACCENT, "markerfacecolor": atlas.ACCENT},
             "tile": {"color": atlas.INK_SOFT, "markerfacecolor": atlas.BG}}
PANEL_TITLE = {"National": "Philippines", "NCR": "Metro Manila (NCR)", "Metro Cebu": "Metro Cebu",
               "Metro Davao": "Metro Davao"}
UNIT_LABEL = {"barangay": "Barangays (main unit in the cities; check nationally)",
              "tile": "RWI tiles (main unit nationally; low-n check in the cities)"}
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
    return fig


def quintile_chart(q):
    """q: the quintile_rates table. One panel per scope, on one shared scale."""
    q = q[q.quintile != "All"].assign(quintile=lambda d: d.quintile.astype(int))
    top = q.outlets_per_100k.max()
    with plt.rc_context(atlas.style()):
        fig = _figure((9, 4.1))
        axes = fig.subplots(1, len(QUINTILE_PANELS), sharey=True)
        for ax, (scope, unit, name, unit_name) in zip(axes, QUINTILE_PANELS):
            d = q[(q.scope == scope) & (q.unit == unit)].sort_values("quintile")
            ax.bar(d.quintile, d.outlets_per_100k, width=0.68, color=atlas.ACCENT, zorder=2)
            for x, v in zip(d.quintile, d.outlets_per_100k):
                ax.text(x, v + top * 0.025, f"{v:.1f}", ha="center", va="bottom", color=atlas.INK,
                        **atlas.mono(7.5, bold=True))
            atlas.bare(ax)
            atlas.baseline(ax)
            ax.set_ylim(0, top * 1.14)
            ax.set_xlim(0.4, 5.6)
            ax.set_yticks([])
            ax.set_xticks(range(1, 6), ["Q1\npoorest", "Q2", "Q3", "Q4", "Q5\nrichest"],
                          fontfamily=atlas.family(atlas.MONO), fontsize=7.5)
            ax.set_title(f"{name}\n", loc="left", **atlas.head(10.5))
            ax.text(0, 1.0, unit_name, transform=ax.transAxes, va="bottom", color=atlas.MUTED,
                    **atlas.mono(7.5))
        top_room = atlas.heading(fig, "Lotto outlets per 100,000 people, by wealth fifth",
                                 "Each scope's people split into fifths by wealth; each city by its own people. "
                                 "No controls.")
        fig.tight_layout(rect=(0, 0, 1, top_room), w_pad=2.2)
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
    with plt.rc_context(atlas.style()):
        fig = _figure((2.35 * len(scopes) + 2.4, 0.42 * len(rows) + 2.2))
        axes = fig.subplots(1, len(scopes), sharey=True)
        for ax, scope in zip(axes, scopes):
            for j, (model, variant) in enumerate(rows):
                y = len(rows) - 1 - j
                for unit in ("barangay", "tile"):
                    d = m[(m.model == model) & (m.variant == variant) & (m.scope == scope) & (m.unit == unit)]
                    if d.empty:
                        continue
                    r = d.iloc[0]
                    yy = y + (0.14 if unit == "barangay" else -0.14)
                    mark = UNIT_MARK[unit]
                    ax.plot([r.ci_low, r.ci_high], [yy] * 2, color=mark["color"], linewidth=1.9,
                            solid_capstyle="butt")
                    ax.plot(r.wealth_ratio, yy, "s", markersize=4.6, markeredgewidth=1.4,
                            markeredgecolor=mark["color"], markerfacecolor=mark["markerfacecolor"])
            ax.axvline(1, color=atlas.INK, linewidth=1.1, linestyle=(0, (3, 3)))
            ax.set_xscale("log")
            ax.set_xlim(lo, hi)
            ax.set_ylim(-0.6, len(rows) - 0.4)
            ax.set_xticks(ticks, [f"{t:g}×" if t == 1 else f"{t:g}" for t in ticks],
                          fontfamily=atlas.family(atlas.MONO), fontsize=7.5)
            ax.minorticks_off()
            atlas.bare(ax)
            ax.spines["bottom"].set_visible(True)
            ax.spines["bottom"].set_linewidth(1.5)
            ax.tick_params(axis="x", length=3.5, width=1.1, color=atlas.INK)
            ax.set_title(PANEL_TITLE[scope], loc="left", **atlas.head(10.5))
        axes[0].set_yticks(range(len(rows)), [ROW_LABEL[r] for r in rows][::-1], fontsize=8.5)
        top_room = atlas.heading(fig, "Wealth ratio by model variant, with 95% intervals",
                                 "Per 1 national SD of RWI, log scale. Above 1: more outlets per person in richer "
                                 "places. The dashed line at 1 is no association.")
        handles = [plt.Line2D([], [], marker="s", linewidth=1.9, markersize=4.6, markeredgewidth=1.4,
                              markeredgecolor=UNIT_MARK[u]["color"], label=UNIT_LABEL[u], **UNIT_MARK[u])
                   for u in ("barangay", "tile")]
        fig.legend(handles=handles, loc="lower left", ncol=2, fontsize=8, bbox_to_anchor=(0.005, 0.0))
        fig.tight_layout(rect=(0, 0.06, 1, top_room))
        fig.savefig(FIGURES / "rate_ratios.png")
    return FIGURES / "rate_ratios.png"
