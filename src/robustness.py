#!/usr/bin/env python3
"""
Robustness check for the mapping-completeness confound.

The national result (outlets rise with wealth) is vulnerable to OSM being better
mapped in rich/urban areas. Metro Manila (NCR) is uniformly urban and among the
best-mapped places in the country, yet spans rich and poor barangays. If the
positive wealth gradient survives inside NCR, it is not purely a mapping artefact.

Run after analysis.py:  python src/robustness.py
"""
import json
import math
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.stats import spearmanr
from shapely.geometry import Point

from common import DERIVED, WORK, ncr_boundary, weighted_quantiles

warnings.filterwarnings("ignore")


def sig(x):
    return float(f"{x:.6g}")


cells = pd.read_csv(WORK / "analysis_cells.csv")
cells["clon"] = (cells.min_lon + cells.max_lon) / 2
cells["clat"] = (cells.min_lat + cells.max_lat) / 2

ncr = ncr_boundary()
print("NCR match:", ncr["NAME_1"].tolist())
ncr_geom = ncr.union_all()

gcells = gpd.GeoDataFrame(cells, geometry=[Point(xy) for xy in zip(cells.clon, cells.clat)], crs=4326)
ncr_cells = gcells[gcells.geometry.within(ncr_geom) & (gcells["pop"] > 0)].copy()
print(f"\nNCR cells (pop>0): {len(ncr_cells):,}   population: {ncr_cells['pop'].sum():,.0f}   "
      f"outlets: {ncr_cells['n_outlets'].sum():,}")

# quintiles within NCR (fewer cells -> 5 bins for stability)
ncr_cells["q"] = weighted_quantiles(ncr_cells["rwi"].values, ncr_cells["pop"].values, 5)
g = ncr_cells.groupby("q").agg(cells=("rwi", "size"), rwi_mean=("rwi", "mean"),
                               population=("pop", "sum"), outlets=("n_outlets", "sum")).reset_index()
g["outlets_per_100k"] = g.outlets / g.population * 1e5
g["quintile"] = g["q"] + 1
g = g[["quintile", "cells", "rwi_mean", "population", "outlets", "outlets_per_100k"]]
g.round({"rwi_mean": 4, "population": 0, "outlets_per_100k": 4}).to_csv(
    DERIVED / "ncr_quintiles.csv", index=False)
print("\n=== Within NCR: outlets per 100k by wealth quintile (1=poorest, 5=richest) ===")
print(g.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
rho, p = spearmanr(g.quintile, g.outlets_per_100k)
print(f"Spearman(quintile, per100k) within NCR: rho={rho:.3f}  p={p:.3f}")

# NB model within NCR
r = ncr_cells[ncr_cells["pop"] >= 50].copy()
r["rwi_z"] = (r.rwi - r.rwi.mean()) / r.rwi.std()
r["logpop"] = np.log(r["pop"])
m = smf.glm("n_outlets ~ rwi_z", data=r, family=sm.families.NegativeBinomial(alpha=1.0),
            offset=r["logpop"]).fit()
coef = m.params["rwi_z"]
lo, hi = m.conf_int().loc["rwi_z"]
print(f"\nNCR NB model  n_outlets~RWI (offset log pop):  IRR(+1 SD)={math.exp(coef):.3f}  "
      f"95% CI=[{math.exp(lo):.3f}, {math.exp(hi):.3f}]  p={m.pvalues['rwi_z']:.2e}  (n={len(r)})")

with open(DERIVED / "ncr_robustness.json", "w") as fh:
    json.dump({
        "ncr_cells": int(len(ncr_cells)), "ncr_pop": sig(ncr_cells["pop"].sum()),
        "ncr_outlets": int(ncr_cells["n_outlets"].sum()),
        "ncr_spearman_rho": sig(rho), "ncr_spearman_p": sig(p),
        "ncr_nb_irr": sig(math.exp(coef)), "ncr_nb_ci": [sig(math.exp(lo)), sig(math.exp(hi))],
        "ncr_nb_p": sig(m.pvalues["rwi_z"]), "ncr_nb_n_cells": int(len(r)),
    }, fh, indent=2)
    fh.write("\n")
print("\nWritten data/derived/ncr_robustness.json and data/derived/ncr_quintiles.csv")
