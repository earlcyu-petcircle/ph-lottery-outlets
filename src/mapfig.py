#!/usr/bin/env python3
"""Static map figure: the paper's print map. Run after analysis.py."""
import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.cm import ScalarMappable  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402

from common import (BG, CANVAS, DERIVED, FIGURES, INK, MUTED, OUTLET_EDGE, OUTLET_FILL, RAW,  # noqa: E402
                    RULE, WEALTH, ncr_boundary, rwi_canvas)

plt.rcParams.update({"font.family": "serif", "font.serif": ["Georgia", "DejaVu Serif"],
                     "figure.facecolor": BG, "savefig.facecolor": BG, "text.color": INK})

odf = pd.read_csv(DERIVED / "outlets_clean.csv")
grid, vmin, vmax = rwi_canvas(res=0.02)
norm = Normalize(vmin, vmax)
adm0 = gpd.read_file(RAW / "gadm41_PHL.gpkg", layer="ADM_ADM_0")
ncr = ncr_boundary()

fig = plt.figure(figsize=(11, 6.6))
gs = fig.add_gridspec(1, 2, width_ratios=[1.55, 1], wspace=0.08)
axm, axz = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

extent = [CANVAS["lon_min"], CANVAS["lon_max"], CANVAS["lat_min"], CANVAS["lat_max"]]
for ax in (axm, axz):
    ax.imshow(grid, extent=extent, origin="upper", cmap=WEALTH, norm=norm,
              interpolation="nearest", zorder=1)
    adm0.boundary.plot(ax=ax, color=INK, linewidth=0.4, zorder=2)
    ax.set_facecolor(BG)

axm.scatter(odf.lon, odf.lat, s=6, c=OUTLET_FILL, edgecolor=OUTLET_EDGE, linewidth=0.2, zorder=3, alpha=0.9)
ncr.boundary.plot(ax=axm, color=INK, linewidth=1.0, zorder=4)
axm.set_xlim(116.8, 127.0)
axm.set_ylim(4.5, 21.3)
axm.set_title("Wealth base + lotto outlets, Philippines", fontsize=13, loc="left", pad=6)

axz.scatter(odf.lon, odf.lat, s=22, c=OUTLET_FILL, edgecolor=OUTLET_EDGE, linewidth=0.3, zorder=3, alpha=0.92)
ncr.boundary.plot(ax=axz, color=INK, linewidth=1.2, zorder=4)
axz.set_xlim(120.9, 121.14)
axz.set_ylim(14.35, 14.78)
axz.set_title("Zoom: Metro Manila (NCR)", fontsize=13, loc="left", pad=6)

for ax in (axm, axz):  # after the GeoPandas plots, which add their own axis labels
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")

sm = ScalarMappable(norm=norm, cmap=WEALTH)
sm.set_array([])
cb = fig.colorbar(sm, ax=[axm, axz], fraction=0.025, pad=0.02, aspect=30)
cb.set_label("Relative Wealth Index  (poorer -> richer)", fontsize=9, color=MUTED)
cb.ax.tick_params(labelsize=8, color=RULE)
fig.savefig(FIGURES / "fig_map_static.png", dpi=175, bbox_inches="tight", metadata={"Software": None})
print(f"wrote figures/fig_map_static.png  |  outlets: {len(odf)}")
