#!/usr/bin/env python3
"""
The numbered figures in section 6 (Results) of docs/paper.md, one per research question and
method, drawn from the committed tables in results/tables/ and saved to results/figures/:

  RQ1, outlets per person (national, 2.4 km tiles; barangays alongside as the check)
    fig01_rq1_outlet_rate.png     outlets per 100,000 people by wealth quintile
    fig02_rq1_no_outlet.png       share of people living in a tile with no outlet
    fig03_rq1_shops_urban.png     shops per 1,000 people and urban share
    fig04_rq1_count_model.png     negative binomial wealth rate ratio by control step
    fig05_rq1_presence_model.png  logistic (any outlet) wealth odds ratio
    fig06_rq1_checks.png          spatial refits and outlet sensitivities
  RQ2, within Metro Manila, Metro Cebu and Metro Davao (each city's own barangay quintiles)
    fig07_rq2_outlet_rate.png     outlets per 100,000 people
    fig08_rq2_shops.png           shops per 1,000 people
    fig09_rq2_count_model.png     negative binomial wealth rate ratio by control step
    fig10_rq2_presence_model.png  logistic (any outlet) wealth odds ratio
    fig11_rq2_checks.png          tile models and spatial refits
  RQ3, road distance to the nearest outlet
    fig12_rq3_road_national.png   median road distance and share within 2 km, national
    fig13_rq3_road_cities.png     median road distance in each city
    fig14_rq3_straight_line.png   median road against straight-line distance, national

Each chart's title is the headline result and its subtitle says what it shows: measure, unit,
grouping and source. The numbers in titles are read from the tables, so a rerun that moves
them moves the titles too. Quintile axes run Q1 (poorest fifth of people) to Q5 (richest).
Ratios are per national standard deviation of RWI (0.49 points), on a log scale.

Run by 03_analyse.sh after the notebooks; also runs on its own:
  .venv/bin/python src/03_analyse/results_figures.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

import atlas
from analysis_samples import FIGURES, TABLES

CITIES = [("NCR", "Metro Manila"), ("Metro Cebu", "Metro Cebu"), ("Metro Davao", "Metro Davao")]
QUINTILES = ["Q1", "Q2", "Q3", "Q4", "Q5"]
Q_NOTE = "Q1 is the poorest fifth of people, Q5 the richest."
RATIO_NOTE = "Per national standard deviation of RWI (0.49 points), 95% intervals, log scale; 1 is no association."
VARIANTS = ["wealth only", "+ urban share", "+ shops", "+ shops and roads"]
# Tiles in cobalt (the national main unit), barangays in ink and hollow, as in charts.py
MARK = {"tile": {"color": atlas.ACCENT, "face": atlas.ACCENT},
        "barangay": {"color": atlas.INK_SOFT, "face": atlas.BG}}
SECONDARY = atlas.CATEGORICAL[2]  # amber, the second series in a grouped bar chart


def _figure(size):
    """A figure on its own Agg canvas, outside pyplot."""
    fig = Figure(figsize=size, dpi=200)
    FigureCanvasAgg(fig)
    return fig


def _save(fig, name):
    path = FIGURES / name
    fig.savefig(path)
    return path


def _ci(r):
    return f"{r.wealth_ratio:.2f} ({r.ci_low:.2f}-{r.ci_high:.2f})"


def _quintiles(q, scope, unit):
    d = q[(q.scope == scope) & (q.unit == unit) & (q.quintile != "All")]
    return d.assign(quintile=d.quintile.astype(int)).sort_values("quintile").set_index("quintile")


def _model(m, scope, unit, model, variant):
    d = m[(m.scope == scope) & (m.unit == unit) & (m.model == model) & (m.variant == variant)]
    return d.iloc[0] if len(d) else None


def _bars(ax, values, fmt, top=None, color=atlas.ACCENT, title=None):
    """Quintile bars on a 2px baseline with mono value labels, no gridlines or y axis."""
    values = list(values)
    top = top or max(values)
    xs = range(1, len(values) + 1)
    ax.bar(xs, values, width=0.66, color=color, zorder=2)
    for x, v in zip(xs, values):
        ax.text(x, v + top * 0.03, fmt(v), ha="center", va="bottom", color=atlas.INK, **atlas.mono(8, bold=True))
    atlas.bare(ax)
    atlas.baseline(ax)
    ax.set_ylim(0, top * 1.16)
    ax.set_xlim(0.4, len(values) + 0.6)
    ax.set_yticks([])
    ax.set_xticks(list(xs), QUINTILES[:len(values)], fontfamily=atlas.family(atlas.MONO), fontsize=8.5)
    if title:
        ax.set_title(title, loc="left", **atlas.head(10.5))


def _bar_figure(name, kick, title, subtitle, panels, width=7.2, height=3.9):
    """panels: (panel title or None, values, label format, shared top or None, colour)."""
    with plt.rc_context(atlas.style()):
        fig = _figure((width, height))
        axes = fig.subplots(1, len(panels), squeeze=False)[0]
        for ax, (ptitle, values, fmt, top, color) in zip(axes, panels):
            _bars(ax, values, fmt, top=top, color=color, title=ptitle)
        room = atlas.heading(fig, title, subtitle, kick=kick)
        fig.tight_layout(rect=(0, 0, 1, room), w_pad=2.5)
        return _save(fig, name)


def _dots(ax, rows, lo, hi, labels=True):
    """rows: (y, model row, unit). A square at the ratio and a bar across its 95% interval."""
    for y, r, unit in rows:
        if r is None:
            continue
        mk = MARK[unit]
        ax.plot([r.ci_low, r.ci_high], [y, y], color=mk["color"], linewidth=1.9, solid_capstyle="butt", zorder=2)
        ax.plot(r.wealth_ratio, y, "s", markersize=5, markeredgewidth=1.4, markeredgecolor=mk["color"],
                markerfacecolor=mk["face"], zorder=3)
        if labels:
            ax.text(min(r.ci_high, hi) * 1.06, y, _ci(r), va="center", color=atlas.INK, **atlas.mono(7))
    ax.axvline(1, color=atlas.INK, linewidth=1.1, linestyle=(0, (3, 3)), zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(lo, hi)
    ticks = [t for t in (0.25, 0.5, 1, 2, 4, 8, 16) if lo <= t <= hi]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks], fontfamily=atlas.family(atlas.MONO), fontsize=7.5)
    ax.minorticks_off()
    ax.tick_params(axis="x", labelfontfamily=atlas.family(atlas.MONO))
    atlas.bare(ax)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.tick_params(axis="x", length=3.5, width=1.1, color=atlas.INK)


def _legend(fig, units):
    labels = {"tile": "2.4 km tiles", "barangay": "Barangays"}
    handles = [plt.Line2D([], [], marker="s", linewidth=1.9, markersize=5, markeredgewidth=1.4,
                          color=MARK[u]["color"], markeredgecolor=MARK[u]["color"],
                          markerfacecolor=MARK[u]["face"], label=labels[u]) for u in units]
    fig.legend(handles=handles, loc="lower left", ncol=len(units), fontsize=8, bbox_to_anchor=(0.005, 0.0))


def _dot_figure(name, kick, title, subtitle, panels, row_labels, lo, hi, units, width=7.6, labels=True):
    """panels: (panel title or None, [(row index, model row, unit)]). Row 0 is drawn at the top."""
    n = len(row_labels)
    with plt.rc_context(atlas.style()):
        fig = _figure((width, 0.42 * n * (1 if len(panels) == 1 else 1.1) + 2.3))
        axes = fig.subplots(1, len(panels), sharey=True, squeeze=False)[0]
        for ax, (ptitle, rows) in zip(axes, panels):
            _dots(ax, [(n - 1 - i + off, r, u) for i, r, u, off in rows], lo, hi, labels=labels)
            ax.set_ylim(-0.6, n - 0.4)
            if ptitle:
                ax.set_title(ptitle, loc="left", **atlas.head(10.5))
        axes[0].set_yticks(range(n), row_labels[::-1], fontsize=8.5)
        room = atlas.heading(fig, title, subtitle, kick=kick)
        if units:
            _legend(fig, units)
        fig.tight_layout(rect=(0, 0.07 if units else 0, 1, room), w_pad=1.5)
        return _save(fig, name)


# RQ1 ---------------------------------------------------------------------------------------

def rq1_outlet_rate(q):
    t = _quintiles(q, "National", "tile")
    r = t.outlets_per_100k
    return _bar_figure(
        "fig01_rq1_outlet_rate.png", "Figure 1 / RQ1 / Descriptive statistics",
        f"The richest quintile has {r[5] / r[1]:.0f} times the outlets per person of the poorest",
        f"Lotto outlets per 100,000 people by national wealth quintile, on 2.4 km RWI tiles. {Q_NOTE}\n"
        "Source: PCSO outlet map, PSA 2024 census, Meta RWI (results/tables/quintile_rates.csv).",
        [(None, r, lambda v: f"{v:.1f}", None, atlas.ACCENT)])


def rq1_no_outlet(q):
    s = _quintiles(q, "National", "tile").share_people_in_units_no_outlet * 100
    return _bar_figure(
        "fig02_rq1_no_outlet.png", "Figure 2 / RQ1 / Descriptive statistics",
        f"{s[1]:.1f}% of people in Q1 live in a tile with no outlet, against {s[5]:.1f}% in Q5",
        "Share of people living in a 2.4 km RWI tile with no lotto outlet, by national wealth quintile.\n"
        f"{Q_NOTE} Source: results/tables/quintile_rates.csv.",
        [(None, s, lambda v: f"{v:.1f}%", 100, atlas.ACCENT)])


def rq1_shops_urban(q):
    t = _quintiles(q, "National", "tile")
    shops, urban = t.shops_per_1k, t.urban_share_people * 100
    return _bar_figure(
        "fig03_rq1_shops_urban.png", "Figure 3 / RQ1 / Descriptive statistics",
        f"The richest quintile has {shops[5] / shops[1]:.0f} times the shops per person of the poorest",
        f"Left: shops per 1,000 people (OpenStreetMap and Overture). Right: share of people in GHSL urban cells.\n"
        f"By national wealth quintile, on 2.4 km RWI tiles. {Q_NOTE} Source: results/tables/quintile_rates.csv.",
        [("Shops per 1,000 people", shops, lambda v: f"{v:.2f}", None, atlas.ACCENT),
         ("People in urban cells", urban, lambda v: f"{v:.0f}%" if v < 99.5 else f"{v:.1f}%", 100, atlas.ACCENT)],
        width=8.2)


def rq1_count_model(m):
    rows = []
    for i, v in enumerate(VARIANTS):
        rows.append((i, _model(m, "National", "tile", "count", v), "tile", 0.15))
        rows.append((i, _model(m, "National", "barangay", "count", v), "barangay", -0.15))
    first = _model(m, "National", "tile", "count", "wealth only")
    last = _model(m, "National", "tile", "count", "+ shops and roads")
    return _dot_figure(
        "fig04_rq1_count_model.png", "Figure 4 / RQ1 / Negative binomial regression",
        f"The wealth rate ratio falls from {first.wealth_ratio:.2f} with no controls to "
        f"{last.wealth_ratio:.2f} with every control",
        "Outlets per person, wealth rate ratio by control step; province intercepts in every step.\n"
        f"{RATIO_NOTE}\nSource: results/tables/models.csv.",
        [(None, rows)], ["Wealth only", "+ urban share", "+ shops", "+ shops and roads"], 0.8, 5,
        ["tile", "barangay"])


def rq1_presence_model(m):
    rows = []
    for i, v in enumerate(["+ urban share", "+ shops"]):
        rows.append((i, _model(m, "National", "tile", "presence", v), "tile", 0.15))
        rows.append((i, _model(m, "National", "barangay", "presence", v), "barangay", -0.15))
    a = _model(m, "National", "tile", "presence", "+ urban share")
    b = _model(m, "National", "tile", "presence", "+ shops")
    return _dot_figure(
        "fig05_rq1_presence_model.png", "Figure 5 / RQ1 / Logistic regression",
        f"Wealth odds ratio of any outlet: {a.wealth_ratio:.2f} with urban share, {b.wealth_ratio:.2f} with shops",
        "Odds of at least one outlet, wealth odds ratio; log population and province intercepts in both.\n"
        f"{RATIO_NOTE}\nSource: results/tables/models.csv.",
        [(None, rows)], ["+ urban share", "+ shops"], 0.8, 5, ["tile", "barangay"])


CHECKS = [("count", "Main model"), ("count, spatial refit", "Spatial refit"),
          ("count, sensitivity: GPS points consistent with their address only", "GPS matches address only"),
          ("count, sensitivity: adding outlets placed only at a town centre", "+ town-centre outlets")]


def rq1_checks(m):
    panels, vals = [], {}
    for v in ["+ urban share", "+ shops"]:
        rows = [(i, _model(m, "National", "tile", model, v), "tile", 0) for i, (model, _) in enumerate(CHECKS)]
        vals[v] = [r.wealth_ratio for _, r, _, _ in rows]
        panels.append((f"Tiles, {v}", rows))
    rng = lambda xs: f"{min(xs):.2f}-{max(xs):.2f}"
    return _dot_figure(
        "fig06_rq1_checks.png", "Figure 6 / RQ1 / Spatial checks and outlet sensitivities",
        f"Across the checks the tile ratio stays at {rng(vals['+ urban share'])} with urban share "
        f"and {rng(vals['+ shops'])} with shops",
        "Negative binomial wealth rate ratio on 2.4 km tiles: the main model, a refit with 10 Moran eigenvectors,\n"
        "only GPS points that match their address, and adding the outlets placed only at a town centre.\n"
        f"{RATIO_NOTE} Source: results/tables/models.csv.",
        panels, [label for _, label in CHECKS], 0.9, 3.2, None, width=8.6)


# RQ2 ---------------------------------------------------------------------------------------

def rq2_outlet_rate(q):
    rates = {name: _quintiles(q, scope, "barangay").outlets_per_100k for scope, name in CITIES}
    top = max(r.max() for r in rates.values())
    mm, dv = rates["Metro Manila"], rates["Metro Davao"]
    return _bar_figure(
        "fig07_rq2_outlet_rate.png", "Figure 7 / RQ2 / Descriptive statistics",
        f"Outlets per 100,000: {mm.min():.1f} to {mm.max():.1f} in every Metro Manila quintile, "
        f"{dv[1]:.1f} to {dv[5]:.1f} in Metro Davao",
        f"Lotto outlets per 100,000 people by each city's own barangay wealth quintile. {Q_NOTE}\n"
        "Source: results/tables/quintile_rates.csv.",
        [(name, r, lambda v: f"{v:.1f}", top, atlas.ACCENT) for name, r in rates.items()], width=9)


def rq2_shops(q):
    shops = {name: _quintiles(q, scope, "barangay").shops_per_1k for scope, name in CITIES}
    top = max(r.max() for r in shops.values())
    peak = [f"Q{s.idxmax()} in {name}" for name, s in shops.items()]
    return _bar_figure(
        "fig08_rq2_shops.png", "Figure 8 / RQ2 / Descriptive statistics",
        f"Shops per person peak in {peak[0]}, {peak[1]} and {peak[2]}",
        f"Shops per 1,000 people (OpenStreetMap and Overture) by each city's own barangay wealth quintile. {Q_NOTE}\n"
        "Source: results/tables/quintile_rates.csv.",
        [(name, s, lambda v: f"{v:.1f}", top, atlas.ACCENT) for name, s in shops.items()], width=9)


def rq2_count_model(m):
    panels = []
    for scope, name in CITIES:
        panels.append((name, [(i, _model(m, scope, "barangay", "count", v), "barangay", 0)
                              for i, v in enumerate(VARIANTS)]))
    return _dot_figure(
        "fig09_rq2_count_model.png", "Figure 9 / RQ2 / Negative binomial regression",
        "Every Metro Davao interval sits above 1; every Metro Manila interval includes 1",
        "Outlets per person, wealth rate ratio by control step, on barangays; city and municipality intercepts,\n"
        f"errors clustered by RWI tile. {RATIO_NOTE}\nSource: results/tables/models.csv.",
        panels, ["Wealth only", "+ urban share", "+ shops", "+ shops and roads"], 0.5, 10, None, width=9.4,
        labels=False)


def rq2_presence_model(m):
    panels, shops = [], []
    for scope, name in CITIES:
        panels.append((name, [(i, _model(m, scope, "barangay", "presence", v), "barangay", 0)
                              for i, v in enumerate(["+ urban share", "+ shops"])]))
        shops.append(f"{name.removeprefix('Metro ')} {_model(m, scope, 'barangay', 'presence', '+ shops').wealth_ratio:.2f}")
    return _dot_figure(
        "fig10_rq2_presence_model.png", "Figure 10 / RQ2 / Logistic regression",
        f"Odds ratio of any outlet with shops: {shops[0]}, {shops[1]}, {shops[2]}",
        "Odds of at least one outlet, wealth odds ratio, on barangays; log population, city and municipality\n"
        f"intercepts, errors clustered by RWI tile. {RATIO_NOTE}\nSource: results/tables/models.csv.",
        panels, ["+ urban share", "+ shops"], 0.3, 16, None, width=9.4, labels=False)


def rq2_checks(m):
    labels = [f"Tiles: {v}" for v in VARIANTS] + ["Spatial refit: + urban share", "Spatial refit: + shops"]
    panels, shops = [], []
    for scope, name in CITIES:
        rows = [(i, _model(m, scope, "tile", "count", v), "tile", 0) for i, v in enumerate(VARIANTS)]
        for j, v in enumerate(["+ urban share", "+ shops"]):
            for unit in ("barangay", "tile"):
                r = _model(m, scope, unit, "count, spatial refit", v)
                if r is not None:
                    rows.append((4 + j, r, unit, 0))
        panels.append((name, rows))
        shops.append(f"{_model(m, scope, 'tile', 'count', '+ shops').wealth_ratio:.2f} in {name}")
    return _dot_figure(
        "fig11_rq2_checks.png", "Figure 11 / RQ2 / Tile models and spatial refits",
        f"On tiles with shops, the rate ratio is {shops[0]}, {shops[1]} and {shops[2]}",
        f"Negative binomial wealth rate ratio on each city's 2.4 km tiles, and refits with Moran eigenvectors\n"
        f"(barangays in Metro Manila and Metro Cebu, tiles in Metro Davao). {RATIO_NOTE}\n"
        "Source: results/tables/models.csv.",
        panels, labels, 0.5, 8, ["tile", "barangay"], width=9.4, labels=False)


# RQ3 ---------------------------------------------------------------------------------------

def _road(rd, scope):
    d = rd[(rd.scope == scope) & (rd.quintile != "All")]
    return d.assign(quintile=d.quintile.astype(int)).sort_values("quintile").set_index("quintile")


def rq3_road_national(rd):
    n = _road(rd, "National")
    return _bar_figure(
        "fig12_rq3_road_national.png", "Figure 12 / RQ3 / Road distance",
        f"The median person in Q1 lives {n.road_km_median[1]:.1f} km from an outlet by road; in Q5, "
        f"{n.road_km_median[5]:.1f} km",
        f"Left: median road distance to the nearest outlet, km. Right: share of people within 2 km by road.\n"
        f"Shortest paths on OpenStreetMap roads from 100 m population pixels, by national wealth quintile.\n"
        f"{Q_NOTE} Source: results/tables/road_distance.csv.",
        [("Median road distance, km", n.road_km_median, lambda v: f"{v:.1f}", None, atlas.ACCENT),
         ("People within 2 km by road", n.share_people_within_2km_road * 100, lambda v: f"{v:.0f}%", 100,
          atlas.ACCENT)],
        width=8.2, height=4.1)


def rq3_road_cities(rd):
    med = {name: _road(rd, scope).road_km_median for scope, name in CITIES}
    top = max(r.max() for r in med.values())
    mm, dv = med["Metro Manila"], med["Metro Davao"]
    return _bar_figure(
        "fig13_rq3_road_cities.png", "Figure 13 / RQ3 / Road distance",
        f"Median road distance: {mm.min():.1f} to {mm.max():.1f} km in every Metro Manila quintile, "
        f"{dv[1]:.1f} to {dv[5]:.1f} km in Metro Davao",
        f"Median road distance to the nearest outlet, km, by each city's own barangay wealth quintile. {Q_NOTE}\n"
        "Source: results/tables/road_distance.csv.",
        [(name, r, lambda v: f"{v:.1f}", top, atlas.ACCENT) for name, r in med.items()], width=9)


def rq3_straight_line(rd):
    n = _road(rd, "National")
    xs = range(1, 6)
    w = 0.36
    with plt.rc_context(atlas.style()):
        fig = _figure((7.2, 4.0))
        ax = fig.subplots()
        top = n.road_km_median.max()
        for off, col, color in ((-w / 2, "road_km_median", atlas.ACCENT), (w / 2, "line_km_median", SECONDARY)):
            ax.bar([x + off for x in xs], n[col], width=w, color=color, zorder=2)
            for x, v in zip(xs, n[col]):
                ax.text(x + off, v + top * 0.03, f"{v:.1f}", ha="center", va="bottom", color=atlas.INK,
                        **atlas.mono(7.5, bold=True))
        atlas.bare(ax)
        atlas.baseline(ax)
        ax.set_ylim(0, top * 1.16)
        ax.set_xlim(0.4, 5.6)
        ax.set_yticks([])
        ax.set_xticks(list(xs), QUINTILES, fontfamily=atlas.family(atlas.MONO), fontsize=8.5)
        handles = [plt.Rectangle((0, 0), 1, 1, color=c, label=lab)
                   for c, lab in ((atlas.ACCENT, "By road"), (SECONDARY, "Straight line"))]
        fig.legend(handles=handles, loc="lower left", ncol=2, fontsize=8, bbox_to_anchor=(0.005, 0.0))
        room = atlas.heading(
            fig, f"Straight-line medians run from {n.line_km_median[1]:.1f} km in Q1 to "
                 f"{n.line_km_median[5]:.1f} km in Q5",
            f"Median distance to the nearest outlet, km, by road and in a straight line, by national wealth quintile.\n"
            f"{Q_NOTE} Source: results/tables/road_distance.csv.",
            kick="Figure 14 / RQ3 / Straight-line distance")
        fig.tight_layout(rect=(0, 0.07, 1, room))
        return _save(fig, "fig14_rq3_straight_line.png")


def main():
    q = pd.read_csv(TABLES / "quintile_rates.csv", dtype={"quintile": str})
    m = pd.read_csv(TABLES / "models.csv")
    rd = pd.read_csv(TABLES / "road_distance.csv", dtype={"quintile": str})
    for path in (rq1_outlet_rate(q), rq1_no_outlet(q), rq1_shops_urban(q), rq1_count_model(m),
                 rq1_presence_model(m), rq1_checks(m), rq2_outlet_rate(q), rq2_shops(q), rq2_count_model(m),
                 rq2_presence_model(m), rq2_checks(m), rq3_road_national(rd), rq3_road_cities(rd),
                 rq3_straight_line(rd)):
        print(path.relative_to(FIGURES.parents[1]))


if __name__ == "__main__":
    main()
