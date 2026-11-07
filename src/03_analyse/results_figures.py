#!/usr/bin/env python3
"""
The figures in section 6 (Results) of docs/paper.md (Figures 4 to 17 there), one per research
question and method, drawn from the committed tables in results/tables/ and saved to
results/figures/. The file numbers are the order within section 6, not the paper's numbers:

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

Each chart's kicker says where it sits in the paper, its title is the headline result, its
subtitle is the plain chart title (what is plotted, where), a short note under the chart says how
to read it (what Q1 and Q5 mean, the ratio scale) and a line at the foot names the data sources
(the paper's caption names the table and the method detail). The numbers in titles are read from the tables, so a
rerun that moves them moves the titles too. Quintile axes run Q1 (poorest fifth of people) to Q5
(richest). Ratios are per national standard deviation of RWI (0.49 points), on a log scale.
Colours: cobalt and pink for two series, and one colour per city (atlas.CITY) in every RQ2 and
city RQ3 chart.

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
Q_NOTE = "Q1 is the poorest wealth quintile, Q5 the richest; each holds the same number of people."
RATIO_NOTE = ("Ratio per national standard deviation of RWI (0.49 points), with its 95% interval, on a log scale; "
              "1 is no association.")
CITY_Q_NOTE = f"Each city's barangays split by its own people. {Q_NOTE}"
VARIANTS = ["wealth only", "+ urban share", "+ shops", "+ shops and roads"]
# Tiles in cobalt (the national main unit), barangays in fluoro pink and hollow, as in charts.py;
# in the city charts each city keeps its own colour and the fill tells tiles from barangays
MARK = {"tile": {"color": atlas.ACCENT, "face": atlas.ACCENT},
        "barangay": {"color": atlas.SECOND, "face": atlas.BG}}
KICK = {1: atlas.kick("Results", "RQ1: Outlets per person"), 2: atlas.kick("Results", "RQ2: Within cities"),
        3: atlas.kick("Results", "RQ3: Road distance")}
# The data behind each figure (paper section 3); the paper's caption names the table it is drawn from
_PEOPLE = "PCSO outlet map, Meta RWI, PSA 2024 census on WorldPop"
_MODEL = f"{_PEOPLE}, GHSL, OpenStreetMap, Overture Maps, OCHA COD-AB"
SOURCE = {"rate": f"Source: {_PEOPLE}.",
          "shops": f"Source: {_PEOPLE}, OpenStreetMap, Overture Maps, GHSL.",
          "city rate": f"Source: {_PEOPLE}, OCHA COD-AB.",
          "city shops": f"Source: {_PEOPLE}, OpenStreetMap, Overture Maps, OCHA COD-AB.",
          "model": f"Source: {_MODEL}.",
          "road": f"Source: {_PEOPLE}, OpenStreetMap roads.",
          "city road": f"Source: {_PEOPLE}, OpenStreetMap roads, OCHA COD-AB."}


def _mark(unit, color=None):
    """How a model row is drawn: tiles filled, barangays hollow; color overrides the unit's."""
    mk = MARK[unit]
    if color is None:
        return mk
    return {"color": color, "face": color if mk["face"] != atlas.BG else atlas.BG}


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


def _bar_figure(name, kick, title, subtitle, source, panels, width=7.2, height=3.9, note=Q_NOTE):
    """panels: (panel title or None, values, label format, shared top or None, colour)."""
    with plt.rc_context(atlas.style()):
        fig = _figure((width, height))
        axes = fig.subplots(1, len(panels), squeeze=False)[0]
        for ax, (ptitle, values, fmt, top, color) in zip(axes, panels):
            _bars(ax, values, fmt, top=top, color=color, title=ptitle)
        room = atlas.heading(fig, title, subtitle, kick=kick)
        foot = atlas.source(fig, source, note=note)
        fig.tight_layout(rect=(0, foot, 1, room), w_pad=2.5)
        return _save(fig, name)


def _dots(ax, rows, lo, hi, labels=True):
    """rows: (y, model row, mark). A square at the ratio and a bar across its 95% interval."""
    for y, r, mk in rows:
        if r is None:
            continue
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


def _legend(fig, units, foot, color=None):
    """The unit key above the source line; color draws it in one ink (the city charts)."""
    labels = {"tile": "2.4 km tiles", "barangay": "Barangays"}
    marks = {u: _mark(u, color) for u in units}
    handles = [plt.Line2D([], [], marker="s", linewidth=1.9, markersize=5, markeredgewidth=1.4,
                          color=marks[u]["color"], markeredgecolor=marks[u]["color"],
                          markerfacecolor=marks[u]["face"], label=labels[u]) for u in units]
    fig.legend(handles=handles, loc="lower left", ncol=len(units), fontsize=8, bbox_to_anchor=(0.005, foot))
    return foot + 0.3 / fig.get_figheight()


def _dot_figure(name, kick, title, subtitle, source, panels, row_labels, lo, hi, units, width=7.6, labels=True,
                legend_color=None, note=RATIO_NOTE):
    """panels: (panel title or None, [(row index, model row, mark)]). Row 0 is drawn at the top."""
    n = len(row_labels)
    with plt.rc_context(atlas.style()):
        fig = _figure((width, 0.42 * n * (1 if len(panels) == 1 else 1.1) + 2.4 + 0.15 * note.count("\n")))
        axes = fig.subplots(1, len(panels), sharey=True, squeeze=False)[0]
        for ax, (ptitle, rows) in zip(axes, panels):
            _dots(ax, [(n - 1 - i + off, r, mk) for i, r, mk, off in rows], lo, hi, labels=labels)
            ax.set_ylim(-0.6, n - 0.4)
            if ptitle:
                ax.set_title(ptitle, loc="left", **atlas.head(10.5))
        axes[0].set_yticks(range(n), row_labels[::-1], fontsize=8.5)
        room = atlas.heading(fig, title, subtitle, kick=kick)
        foot = atlas.source(fig, source, note=note)
        if units:
            foot = _legend(fig, units, foot, legend_color)
        fig.tight_layout(rect=(0, foot, 1, room), w_pad=1.5)
        return _save(fig, name)


# RQ1 ---------------------------------------------------------------------------------------

def rq1_outlet_rate(q):
    t = _quintiles(q, "National", "tile")
    r = t.outlets_per_100k
    return _bar_figure(
        "fig01_rq1_outlet_rate.png", KICK[1],
        f"The richest quintile has {r[5] / r[1]:.0f} times the outlets per person of the poorest",
        "Lotto outlets per 100,000 people by wealth quintile, Philippines (2.4 km tiles)",
        SOURCE["rate"], [(None, r, lambda v: f"{v:.1f}", None, atlas.ACCENT)])


def rq1_no_outlet(q):
    s = _quintiles(q, "National", "tile").share_people_in_units_no_outlet * 100
    return _bar_figure(
        "fig02_rq1_no_outlet.png", KICK[1],
        f"{s[1]:.1f}% of people in Q1 live in a tile with no outlet, against {s[5]:.1f}% in Q5",
        "Share of people in a tile with no lotto outlet, by wealth quintile, Philippines",
        SOURCE["rate"], [(None, s, lambda v: f"{v:.1f}%", 100, atlas.ACCENT)])


def rq1_shops_urban(q):
    t = _quintiles(q, "National", "tile")
    shops, urban = t.shops_per_1k, t.urban_share_people * 100
    return _bar_figure(
        "fig03_rq1_shops_urban.png", KICK[1],
        f"The richest quintile has {shops[5] / shops[1]:.0f} times the shops per person of the poorest",
        "Shops per 1,000 people and share of people in urban cells, by wealth quintile, Philippines",
        SOURCE["shops"],
        [("Shops per 1,000 people", shops, lambda v: f"{v:.2f}", None, atlas.ACCENT),
         ("People in urban cells", urban, lambda v: f"{v:.0f}%" if v < 99.5 else f"{v:.1f}%", 100, atlas.SECOND)],
        width=8.2)


def rq1_count_model(m):
    rows = []
    for i, v in enumerate(VARIANTS):
        rows.append((i, _model(m, "National", "tile", "count", v), MARK["tile"], 0.15))
        rows.append((i, _model(m, "National", "barangay", "count", v), MARK["barangay"], -0.15))
    first = _model(m, "National", "tile", "count", "wealth only")
    last = _model(m, "National", "tile", "count", "+ shops and roads")
    return _dot_figure(
        "fig04_rq1_count_model.png", KICK[1],
        f"The wealth rate ratio falls from {first.wealth_ratio:.2f} with no controls to "
        f"{last.wealth_ratio:.2f} with every control",
        "Negative binomial wealth rate ratio by control step, Philippines",
        SOURCE["model"],
        [(None, rows)], ["Wealth only", "+ urban share", "+ shops", "+ shops and roads"], 0.8, 5,
        ["tile", "barangay"])


def rq1_presence_model(m):
    rows = []
    for i, v in enumerate(["+ urban share", "+ shops"]):
        rows.append((i, _model(m, "National", "tile", "presence", v), MARK["tile"], 0.15))
        rows.append((i, _model(m, "National", "barangay", "presence", v), MARK["barangay"], -0.15))
    a = _model(m, "National", "tile", "presence", "+ urban share")
    b = _model(m, "National", "tile", "presence", "+ shops")
    return _dot_figure(
        "fig05_rq1_presence_model.png", KICK[1],
        f"Wealth odds ratio of any outlet: {a.wealth_ratio:.2f} with urban share, {b.wealth_ratio:.2f} with shops",
        "Logistic wealth odds ratio of at least one outlet, Philippines",
        SOURCE["model"],
        [(None, rows)], ["+ urban share", "+ shops"], 0.8, 5, ["tile", "barangay"])


CHECKS = [("count", "Main model"), ("count, spatial refit", "Spatial refit"),
          ("count, sensitivity: GPS points consistent with their address only", "GPS matches address only"),
          ("count, sensitivity: adding outlets placed only at a town centre", "+ town-centre outlets")]


def rq1_checks(m):
    panels, vals = [], {}
    for v, color in (("+ urban share", atlas.ACCENT), ("+ shops", atlas.SECOND)):
        rows = [(i, _model(m, "National", "tile", model, v), _mark("tile", color), 0)
                for i, (model, _) in enumerate(CHECKS)]
        vals[v] = [r.wealth_ratio for _, r, _, _ in rows]
        panels.append((f"Tiles, {v}", rows))
    rng = lambda xs: f"{min(xs):.2f}-{max(xs):.2f}"
    return _dot_figure(
        "fig06_rq1_checks.png", KICK[1],
        f"Across the checks the tile ratio stays at {rng(vals['+ urban share'])} with urban share "
        f"and {rng(vals['+ shops'])} with shops",
        "Tile wealth rate ratio across spatial refits and outlet sensitivities, Philippines",
        SOURCE["model"],
        panels, [label for _, label in CHECKS], 0.9, 3.2, None, width=8.6)


# RQ2 ---------------------------------------------------------------------------------------

def rq2_outlet_rate(q):
    rates = {name: _quintiles(q, scope, "barangay").outlets_per_100k for scope, name in CITIES}
    top = max(r.max() for r in rates.values())
    mm, dv = rates["Metro Manila"], rates["Metro Davao"]
    return _bar_figure(
        "fig07_rq2_outlet_rate.png", KICK[2],
        f"Outlets per 100,000: {mm.min():.1f} to {mm.max():.1f} in every Metro Manila quintile, "
        f"{dv[1]:.1f} to {dv[5]:.1f} in Metro Davao",
        "Lotto outlets per 100,000 people by barangay wealth quintile, three metro areas",
        SOURCE["city rate"],
        [(name, r, lambda v: f"{v:.1f}", top, atlas.CITY[name]) for name, r in rates.items()], width=9,
        note=CITY_Q_NOTE)


def rq2_shops(q):
    shops = {name: _quintiles(q, scope, "barangay").shops_per_1k for scope, name in CITIES}
    top = max(r.max() for r in shops.values())
    peak = [f"Q{s.idxmax()} in {name}" for name, s in shops.items()]
    return _bar_figure(
        "fig08_rq2_shops.png", KICK[2],
        f"Shops per person peak in {peak[0]}, {peak[1]} and {peak[2]}",
        "Shops per 1,000 people by barangay wealth quintile, three metro areas",
        SOURCE["city shops"],
        [(name, s, lambda v: f"{v:.1f}", top, atlas.CITY[name]) for name, s in shops.items()], width=9,
        note=CITY_Q_NOTE)


def rq2_count_model(m):
    panels = []
    for scope, name in CITIES:
        mk = _mark("barangay", atlas.CITY[name])
        panels.append((name, [(i, _model(m, scope, "barangay", "count", v), mk, 0)
                              for i, v in enumerate(VARIANTS)]))
    return _dot_figure(
        "fig09_rq2_count_model.png", KICK[2],
        "Every Metro Davao interval sits above 1; every Metro Manila interval includes 1",
        "Negative binomial wealth rate ratio by control step, barangays in three metro areas",
        SOURCE["model"],
        panels, ["Wealth only", "+ urban share", "+ shops", "+ shops and roads"], 0.5, 10, None, width=9.4,
        labels=False)


def rq2_presence_model(m):
    panels, shops = [], []
    for scope, name in CITIES:
        mk = _mark("barangay", atlas.CITY[name])
        panels.append((name, [(i, _model(m, scope, "barangay", "presence", v), mk, 0)
                              for i, v in enumerate(["+ urban share", "+ shops"])]))
        shops.append(f"{name.removeprefix('Metro ')} {_model(m, scope, 'barangay', 'presence', '+ shops').wealth_ratio:.2f}")
    return _dot_figure(
        "fig10_rq2_presence_model.png", KICK[2],
        f"Odds ratio of any outlet with shops: {shops[0]}, {shops[1]}, {shops[2]}",
        "Logistic wealth odds ratio of at least one outlet, barangays in three metro areas",
        SOURCE["model"],
        panels, ["+ urban share", "+ shops"], 0.3, 16, None, width=9.4, labels=False)


def rq2_checks(m):
    labels = [f"Tiles: {v}" for v in VARIANTS] + ["Spatial refit: + urban share", "Spatial refit: + shops"]
    panels, shops = [], []
    for scope, name in CITIES:
        color = atlas.CITY[name]
        rows = [(i, _model(m, scope, "tile", "count", v), _mark("tile", color), 0) for i, v in enumerate(VARIANTS)]
        for j, v in enumerate(["+ urban share", "+ shops"]):
            for unit in ("barangay", "tile"):
                r = _model(m, scope, unit, "count, spatial refit", v)
                if r is not None:
                    rows.append((4 + j, r, _mark(unit, color), 0))
        panels.append((name, rows))
        shops.append(f"{_model(m, scope, 'tile', 'count', '+ shops').wealth_ratio:.2f} in {name}")
    return _dot_figure(
        "fig11_rq2_checks.png", KICK[2],
        f"On tiles with shops, the rate ratio is {shops[0]}, {shops[1]} and {shops[2]}",
        "Wealth rate ratio on tiles and in spatial refits, three metro areas",
        SOURCE["model"],
        panels, labels, 0.5, 8, ["tile", "barangay"], width=9.4, labels=False, legend_color=atlas.INK,
        note=f"Spatial refits on barangays in Metro Manila and Metro Cebu, on tiles in Metro Davao.\n{RATIO_NOTE}")


# RQ3 ---------------------------------------------------------------------------------------

def _road(rd, scope):
    d = rd[(rd.scope == scope) & (rd.quintile != "All")]
    return d.assign(quintile=d.quintile.astype(int)).sort_values("quintile").set_index("quintile")


def rq3_road_national(rd):
    n = _road(rd, "National")
    return _bar_figure(
        "fig12_rq3_road_national.png", KICK[3],
        f"The median person in Q1 lives {n.road_km_median[1]:.1f} km from an outlet by road; in Q5, "
        f"{n.road_km_median[5]:.1f} km",
        "Road distance to the nearest lotto outlet by wealth quintile, Philippines",
        SOURCE["road"],
        [("Median road distance, km", n.road_km_median, lambda v: f"{v:.1f}", None, atlas.ACCENT),
         ("People within 2 km by road", n.share_people_within_2km_road * 100, lambda v: f"{v:.0f}%", 100,
          atlas.SECOND)],
        width=8.2, height=4.1)


def rq3_road_cities(rd):
    med = {name: _road(rd, scope).road_km_median for scope, name in CITIES}
    top = max(r.max() for r in med.values())
    mm, dv = med["Metro Manila"], med["Metro Davao"]
    return _bar_figure(
        "fig13_rq3_road_cities.png", KICK[3],
        f"Median road distance: {mm.min():.1f} to {mm.max():.1f} km in every Metro Manila quintile, "
        f"{dv[1]:.1f} to {dv[5]:.1f} km in Metro Davao",
        "Median road distance to the nearest lotto outlet by barangay wealth quintile, three metro areas",
        SOURCE["city road"],
        [(name, r, lambda v: f"{v:.1f}", top, atlas.CITY[name]) for name, r in med.items()], width=9,
        note=CITY_Q_NOTE)


def rq3_straight_line(rd):
    n = _road(rd, "National")
    xs = range(1, 6)
    w = 0.36
    with plt.rc_context(atlas.style()):
        fig = _figure((7.2, 4.1))
        ax = fig.subplots()
        top = n.road_km_median.max()
        for off, col, color in ((-w / 2, "road_km_median", atlas.ACCENT), (w / 2, "line_km_median", atlas.SECOND)):
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
        foot = atlas.source(fig, SOURCE["road"], note=Q_NOTE)
        handles = [plt.Rectangle((0, 0), 1, 1, color=c, label=lab)
                   for c, lab in ((atlas.ACCENT, "By road"), (atlas.SECOND, "Straight line"))]
        fig.legend(handles=handles, loc="lower left", ncol=2, fontsize=8, bbox_to_anchor=(0.005, foot))
        room = atlas.heading(
            fig, f"Straight-line medians run from {n.line_km_median[1]:.1f} km in Q1 to "
                 f"{n.line_km_median[5]:.1f} km in Q5",
            "Median distance to the nearest lotto outlet by road and in a straight line, Philippines",
            kick=KICK[3])
        fig.tight_layout(rect=(0, foot + 0.3 / fig.get_figheight(), 1, room))
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
