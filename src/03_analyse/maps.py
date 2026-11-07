"""
Static choropleth maps of outlet density beside wealth, saved to results/figures/ so they can
be seen without the web map:

  rate_and_wealth_map(scope)  two panels on the same units: outlets per 100,000 people and
                              the RWI, both in quantile classes
                              (map_<scope>_rate_and_wealth.png)
  bivariate_map(scope)        wealth terciles x outlet-rate levels, with a 3 x 3 key: the single
                              picture of the relationship (map_<scope>_bivariate.png); Metro
                              Manila's is Figure 1, the paper's summary image

scope is "national" (every RWI tile) or one of the three cities by barangay: "ncr" (Metro
Manila), "cebu" (Metro Cebu) or "davao" (Metro Davao). The colours and the bivariate classes
are the web map's (src/shared/map_layers.py); the ground, type and headings are the story
site's Atlas Grid (src/shared/atlas.py).

Quantile classes:
- Outlet rate: "no outlet" is its own class, and units with outlets are split into quintiles of
  units by their rate.
- RWI: population-weighted fifths, as in the descriptive tables (each holds a fifth of the
  scope's people; each city is split by its own people).

Used by notebooks/05_maps.ipynb. Each function returns the saved file.
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Patch, Rectangle

import atlas
from analysis_samples import CITIES, FIGURES
from common import DERIVED, WORK
from map_layers import BIV, NO_PEOPLE, RATE, RATE_NONE, RWI, map_classes, tile_polygons

RWI5 = [RWI[0], RWI[1], RWI[3], RWI[5], RWI[6]]  # five of the web map's seven RWI steps
UTM = "EPSG:32651"
CITY = {"ncr": "NCR", "cebu": "Metro Cebu", "davao": "Metro Davao"}  # map scope -> analysis scope
TITLE = {"national": "Philippines, RWI tiles (2.4 km)", "ncr": "Metro Manila (NCR), barangays",
         "cebu": "Metro Cebu, barangays", "davao": "Metro Davao, barangays"}
PLACE = {"national": "the Philippines'", "ncr": "Metro Manila's", "cebu": "Metro Cebu's", "davao": "Metro Davao's"}
UNIT = {"national": "tile", "ncr": "barangay", "cebu": "barangay", "davao": "barangay"}
DPI = {"national": 150, "ncr": 170, "cebu": 170, "davao": 170}
SIZE = {"national": ((12, 8.2), (8, 9.4)), "ncr": ((11, 8.8), (6.8, 9.8)),  # (rate and wealth, bivariate)
        "cebu": ((11, 7.8), (7.6, 9.0)), "davao": ((12, 9.8), (9.6, 8.8))}
LEGEND_ROOM = {"cebu": 0.07, "davao": 0.12}  # figure fraction kept below the panels for their legends (default 0.03)
KEY = {"national": (0.66, 0.62, 0.24, 0.22), "ncr": (0.17, 0.095, 0.24, 0.17),  # bivariate key, figure fractions
       "cebu": (0.66, 0.1, 0.2, 0.17), "davao": (0.78, 0.1, 0.17, 0.17)}
MAP_X = {"ncr": (0.3, 0.68)}  # bivariate map's left edge and width, figure fractions (default 0.02, 0.96)
# Where each map sits in docs/paper.md, for its kicker: Metro Manila's bivariate map is the summary
# image (Figure 1); the rest are listed in Appendix B
APPENDIX = atlas.kick("Appendix B", "Every figure and table")
KICK = {("bivariate", "ncr"): atlas.kick("Summary")}
SOURCE = "Source: PCSO outlet map (2 Nov 2026), PSA 2024 census on WorldPop, Meta RWI (2021), OCHA COD-AB."


def units(scope):
    """The mapped units with rate, quintile and bivariate class, projected to UTM 51N."""
    if scope == "national":
        t = pd.read_csv(DERIVED / "tiles.csv", dtype={"quadkey": str})
        t, overall = map_classes(t)
        g = gpd.GeoDataFrame(t, geometry=tile_polygons(t.quadkey), crs=4326)
    else:
        b = pd.read_csv(DERIVED / "barangays.csv")
        b = b[b.metro == CITIES[CITY[scope]]].reset_index(drop=True)
        b, overall = map_classes(b)
        geoms = gpd.read_parquet(WORK / "barangay_geoms.parquet").set_index("adm4_pcode")
        g = gpd.GeoDataFrame(b, geometry=geoms.geometry.reindex(b.adm4_pcode).to_numpy(), crs=4326)
    return g.to_crs(UTM), overall


def _figure(size):
    fig = Figure(figsize=size)
    FigureCanvasAgg(fig)
    return fig


def _draw(ax, g, colours, scope):
    g.plot(ax=ax, color=colours, linewidth=0.15 if scope in CITY else 0.05,
           edgecolor=atlas.BG if scope in CITY else colours)
    ax.set_axis_off()
    ax.set_aspect("equal")
    ax.margins(0.01)


def _rate_classes(g):
    """Colour and legend for outlets per 100,000: no people, no outlet, quintiles of the rest."""
    rate = g.rate_per_100k
    pos = rate[(g.outlets > 0) & (g["pop"] > 0)]
    edges = np.quantile(pos, [0, .2, .4, .6, .8, 1])
    cls = np.clip(np.searchsorted(edges[1:-1], rate, side="right"), 0, 4)
    colours = np.where(g["pop"] <= 0, NO_PEOPLE, np.where(g.outlets == 0, RATE_NONE, np.array(RATE)[cls]))
    labels = [f"{edges[i]:.1f} to {edges[i + 1]:.1f}" for i in range(4)] + [f"{edges[4]:.1f} or more"]
    handles = [Patch(color=NO_PEOPLE, label="No people"), Patch(color=RATE_NONE, label="No outlet")]
    handles += [Patch(color=RATE[i], label=labels[i]) for i in range(5)]
    return colours, handles


def _rwi_classes(g):
    q = g.quintile
    colours = np.array([RWI5[int(v) - 1] if pd.notna(v) else NO_PEOPLE for v in q])
    handles = [Patch(color=NO_PEOPLE, label="No people or no RWI")]
    for i in range(1, 6):
        r = g.rwi[q == i]
        name = {1: " (poorest)", 5: " (richest)"}.get(i, "")
        handles.append(Patch(color=RWI5[i - 1], label=f"{r.min():.2f} to {r.max():.2f}{name}"))
    return colours, handles


def rate_and_wealth_map(scope):
    g, overall = units(scope)
    with plt.rc_context(atlas.style()):
        fig = _figure(SIZE[scope][0])
        top = atlas.heading(fig, f"PCSO lotto outlets and wealth: {TITLE[scope]}",
                            kick=KICK.get(("rate and wealth", scope), APPENDIX), x=0.02)
        for i, (title, (colours, handles), legend_title) in enumerate((
                ("Outlets per 100,000 people", _rate_classes(g),
                 f"Outlets per 100,000\n(quintiles of units with an outlet;\noverall {overall:.1f})"),
                ("Relative Wealth Index", _rwi_classes(g), "RWI, by wealth quintile"))):
            ax = fig.add_subplot(1, 2, i + 1)
            _draw(ax, g, colours, scope)
            ax.set_title(title, loc="left", **atlas.head(11))
            place = ({"loc": "upper right"} if scope == "national"  # open sea, top right
                     else {"loc": "upper left", "bbox_to_anchor": (0.02, 0.0), "ncol": 2})  # below the panel
            ax.legend(handles=handles, title=legend_title.replace("\n", " ") if scope in CITY else legend_title,
                      fontsize=8, title_fontsize=8.5, alignment="left", **place)
        foot = atlas.source(fig, SOURCE, x=0.02)
        fig.tight_layout(rect=(0, max(LEGEND_ROOM.get(scope, 0.03), foot), 1, top))
        path = FIGURES / f"map_{scope}_rate_and_wealth.png"
        fig.savefig(path, dpi=DPI[scope])
    return path


def _bivariate_key(fig, rect, overall):
    """The 3 x 3 key: columns are wealth terciles, rows outlet levels."""
    ax = fig.add_axes(rect)
    for wi, w in enumerate(("w1", "w2", "w3")):
        for oi, o in enumerate(("o0", "o1", "o2")):
            ax.add_patch(Rectangle((wi, oi), 0.96, 0.96, color=BIV[w + o]))
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 3)
    ax.set_aspect("equal")
    ax.set_xticks([0.48, 1.48, 2.48], ["Poorer", "Middle", "Richer"], fontsize=8.5)
    ax.set_yticks([0.48, 1.48, 2.48], ["No outlet", f"Up to {overall:.1f}", f"Above {overall:.1f}"], fontsize=8.5,
                  fontfamily=atlas.family(atlas.MONO))
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.set_xlabel("Wealth tercile →", fontsize=9, color=atlas.INK)
    ax.set_ylabel("Outlets per 100,000 →", fontsize=9, color=atlas.INK)


def bivariate_map(scope):
    g, overall = units(scope)
    colours = np.array([BIV.get(c, NO_PEOPLE) if isinstance(c, str) else NO_PEOPLE for c in g.bivariate])
    with plt.rc_context(atlas.style()):
        fig = _figure(SIZE[scope][1])
        top = atlas.heading(fig, f"Wealth and outlet density together: {TITLE[scope]}",
                            f"Each {UNIT[scope]} by its wealth tercile and its outlets per 100,000 people against\n"
                            f"{PLACE[scope]} overall rate of {overall:.1f}. Hue is wealth (pink poorer, grey middle,\n"
                            "cobalt richer); depth is outlets (pale: none, deep: above the overall rate).",
                            kick=KICK.get(("bivariate", scope), APPENDIX), x=0.03)
        foot = atlas.source(fig, SOURCE, x=0.03)
        h = 0.11 / fig.get_figheight()  # a swatch about 0.11 inch high, as tall as the text
        y = foot + 0.04 / fig.get_figheight()
        fig.patches.append(Rectangle((0.03, y), h * fig.get_figheight() / fig.get_figwidth(), h,
                                     transform=fig.transFigure, color=NO_PEOPLE, figure=fig))
        fig.text(0.03 + 0.18 / fig.get_figwidth(), y, "No people or no RWI", color=atlas.MUTED, **atlas.mono(6.5))
        left, width = MAP_X.get(scope, (0.02, 0.96))
        bottom = foot + 0.25 / fig.get_figheight()
        ax = fig.add_axes((left, bottom, width, top - bottom - 0.01))
        _draw(ax, g, colours, scope)
        _bivariate_key(fig, KEY[scope], overall)
        path = FIGURES / f"map_{scope}_bivariate.png"
        fig.savefig(path, dpi=DPI[scope])
    return path
