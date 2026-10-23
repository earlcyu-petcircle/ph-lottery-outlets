#!/usr/bin/env python3
"""
Lottery outlets vs neighbourhood wealth in the Philippines.

Tests the "lottery is a tax on the poor" hypothesis spatially: are lotto outlets
over-represented in poorer neighbourhoods once population is controlled for?

Inputs (data/raw/, from fetch_data.sh):
  - Outlets:    OpenStreetMap via Overpass API (shop=lottery + named lotto outlets)
  - Wealth:     Meta / Data for Good Relative Wealth Index (RWI), ~2.4 km grid
  - Population: WorldPop 2020 UN-adjusted 1 km population count raster

Method: every layer is binned onto the RWI native grid (zoom-14 tiles). Each cell then
carries {rwi, population, n_outlets}. We compare outlet density per capita across
population-weighted wealth deciles, and fit a negative-binomial model of outlet count
on wealth with a log-population offset.

Run from the repo root:  python src/analysis.py
"""
import json
import math
import re
import warnings

import numpy as np
import pandas as pd
import rasterio
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.stats import spearmanr

from common import DERIVED, RAW, WORK, lonlat_to_tile, read_rwi, tile_bounds, weighted_quantiles

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# 1. Relative Wealth Index -> base grid keyed by (tx, ty)
# ---------------------------------------------------------------------------
rwi = read_rwi()
rwi["tx"], rwi["ty"] = lonlat_to_tile(rwi["longitude"].values, rwi["latitude"].values)
# one RWI value per tile (dedupe defensively)
rwi = rwi.groupby(["tx", "ty"], as_index=False).agg(
    rwi=("rwi", "mean"), lat=("latitude", "mean"), lon=("longitude", "mean"),
    rwi_err=("error", "mean"))
print(f"RWI grid cells: {len(rwi):,}")


# ---------------------------------------------------------------------------
# 2. Population -> sum WorldPop 1 km pixels into the same tiles
# ---------------------------------------------------------------------------
with rasterio.open(RAW / "phl_pop_1km.tif") as r:
    pop = r.read(1)
    T = r.transform
rows, cols = np.where(pop > 0)                       # only populated pixels (nodata is negative)
vals = pop[rows, cols].astype(float)
xs = T.c + (cols + 0.5) * T.a                        # pixel-centre lon/lat
ys = T.f + (rows + 0.5) * T.e
ptx, pty = lonlat_to_tile(xs, ys)
popcell = (pd.DataFrame({"tx": ptx, "ty": pty, "pop": vals})
           .groupby(["tx", "ty"], as_index=False)["pop"].sum())
national_pop = float(vals.sum())
print(f"National population (sum of raster): {national_pop:,.0f}")


# ---------------------------------------------------------------------------
# 3. Lottery outlets from OSM -> filter, bin into tiles
# ---------------------------------------------------------------------------
osm = json.load(open(RAW / "osm_lottery_ph.json"))
KEEP = re.compile(r"lotto|pcso|sweepstake|small town lottery|\bstl\b", re.I)
outlets = []
for e in osm["elements"]:
    t = e.get("tags", {})
    name = t.get("name", "")
    is_lot = (t.get("shop") == "lottery") or (t.get("lottery") == "yes") or bool(KEEP.search(name))
    if not is_lot:
        continue
    if "lat" in e and "lon" in e:
        lat, lon = e["lat"], e["lon"]
    elif "center" in e:
        lat, lon = e["center"]["lat"], e["center"]["lon"]
    else:
        continue
    outlets.append({"osm_type": e["type"], "osm_id": e["id"], "name": name,
                    "shop": t.get("shop", ""), "operator": t.get("operator", ""),
                    "lat": lat, "lon": lon})
odf = pd.DataFrame(outlets).sort_values(["osm_type", "osm_id"]).reset_index(drop=True)
odf["tx"], odf["ty"] = lonlat_to_tile(odf["lon"].values, odf["lat"].values)
# Small Town Lottery points are a separate network from the PCSO's lotto outlets
odf["is_stl"] = odf["name"].str.contains(r"\bstl\b|small town", case=False, regex=True)
odf.to_csv(DERIVED / "outlets_clean.csv", index=False)
n_pcso_operator = int(odf["operator"].str.contains("PCSO|Charity Sweepstakes", case=False, na=False).sum())
print(f"Overpass elements: {len(osm['elements']):,}   lottery outlets kept: {len(odf):,}  "
      f"(shop=lottery: {(odf.shop == 'lottery').sum()}, operator names PCSO: {n_pcso_operator}, "
      f"named as STL: {odf.is_stl.sum()})")
outcell = odf.groupby(["tx", "ty"], as_index=False).size().rename(columns={"size": "n_outlets"})


# ---------------------------------------------------------------------------
# 4. Assemble cell table: rwi + population + outlets on the SAME grid
# ---------------------------------------------------------------------------
cells = rwi.merge(popcell, on=["tx", "ty"], how="left").merge(outcell, on=["tx", "ty"], how="left")
cells["pop"] = cells["pop"].fillna(0.0)
cells["n_outlets"] = cells["n_outlets"].fillna(0).astype(int)
b = cells.apply(lambda r_: tile_bounds(int(r_.tx), int(r_.ty)), axis=1, result_type="expand")
cells[["min_lon", "min_lat", "max_lon", "max_lat"]] = b
mid_lat = np.radians((cells.min_lat + cells.max_lat) / 2)
cells["area_km2"] = ((cells.max_lon - cells.min_lon) * 111.32 * np.cos(mid_lat)) * \
                    ((cells.max_lat - cells.min_lat) * 110.57)
cells["pop_density"] = cells["pop"] / cells["area_km2"]

outlets_in_grid = int(cells["n_outlets"].sum())
print(f"Outlets falling inside an RWI cell: {outlets_in_grid:,} / {len(odf):,} "
      f"({outlets_in_grid / len(odf):.1%})")
cells.to_csv(WORK / "analysis_cells.csv", index=False)


# ---------------------------------------------------------------------------
# 5. Test A: outlets per 100k by population-weighted wealth decile
# ---------------------------------------------------------------------------
m = cells[cells["pop"] > 0].copy()   # a per-capita denominator must be > 0
m["decile"] = weighted_quantiles(m["rwi"].values, m["pop"].values, 10)
dec = m.groupby("decile").agg(
    cells=("rwi", "size"), rwi_mean=("rwi", "mean"),
    population=("pop", "sum"), outlets=("n_outlets", "sum")).reset_index()
dec["outlets_per_100k"] = dec["outlets"] / dec["population"] * 1e5
dec["decile"] = dec["decile"] + 1   # 1 = poorest ... 10 = richest
dec.round({"rwi_mean": 4, "population": 0, "outlets_per_100k": 4}).to_csv(
    DERIVED / "decile_table.csv", index=False)
print("\n=== Outlets per 100,000 people by wealth decile (1=poorest, 10=richest) ===")
print(dec[["decile", "rwi_mean", "population", "outlets", "outlets_per_100k"]]
      .to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

rho, pval = spearmanr(dec["decile"], dec["outlets_per_100k"])
poorer = dec[dec.decile <= 5]
richer = dec[dec.decile > 5]
poorer_rate = poorer.outlets.sum() / poorer.population.sum() * 1e5
richer_rate = richer.outlets.sum() / richer.population.sum() * 1e5
print(f"\nSpearman(decile, outlets_per_100k) rho={rho:.3f}  p={pval:.4f}")
print(f"Poorer half: {poorer_rate:.3f} outlets/100k   Richer half: {richer_rate:.3f} outlets/100k   "
      f"ratio richer/poorer = {richer_rate / poorer_rate:.2f}x")


# ---------------------------------------------------------------------------
# 6. Test B: negative-binomial model, outlet count ~ wealth, with a log-population
#    offset (i.e. modelling the per-capita rate), and a second model adding log
#    population density to strip out urbanicity. Dispersion is fixed at alpha = 1.
# ---------------------------------------------------------------------------
reg = cells[cells["pop"] >= 50].copy()          # avoid unstable tiny denominators
reg["rwi_z"] = (reg["rwi"] - reg["rwi"].mean()) / reg["rwi"].std()
reg["logpop"] = np.log(reg["pop"])
logdens = np.log(reg["pop_density"])
reg["logdens_z"] = (logdens - logdens.mean()) / logdens.std()
print(f"\nRegression universe (cells, pop>=50): {len(reg):,}   "
      f"outlets: {reg.n_outlets.sum():,}   zero-outlet cells: {(reg.n_outlets == 0).mean():.2%}")


def fit_nb(formula):
    return smf.glm(formula, data=reg, family=sm.families.NegativeBinomial(alpha=1.0),
                   offset=reg["logpop"]).fit()


m1 = fit_nb("n_outlets ~ rwi_z")
m2 = fit_nb("n_outlets ~ rwi_z + logdens_z")


def irr(model, name):
    coef = model.params[name]
    lo, hi = model.conf_int().loc[name]
    return math.exp(coef), [math.exp(lo), math.exp(hi)], float(model.pvalues[name])


with open(WORK / "model_summary.txt", "w") as fh:
    for title, mod in [("Model 1: n_outlets ~ RWI  (offset=log population)", m1),
                       ("Model 2: n_outlets ~ RWI + log(pop density)  (offset=log population)", m2)]:
        fh.write(title + "\n" + str(mod.summary()) + "\n\n")

m1_irr, m1_ci, m1_p = irr(m1, "rwi_z")
m2_irr, m2_ci, m2_p = irr(m2, "rwi_z")
m2d_irr, m2d_ci, m2d_p = irr(m2, "logdens_z")
print("\n=== Negative-binomial models (offset = log population) ===")
for label, (i, ci, p) in [("Model 1 wealth", (m1_irr, m1_ci, m1_p)),
                          ("Model 2 wealth", (m2_irr, m2_ci, m2_p)),
                          ("Model 2 density", (m2d_irr, m2d_ci, m2d_p))]:
    print(f"{label:16s} IRR(per +1 SD)={i:.3f}  95% CI=[{ci[0]:.3f}, {ci[1]:.3f}]  p={p:.2e}")


def sig(x):
    return float(f"{x:.6g}")


headline = {
    "outlets_pull_date": (RAW / "pull_date.txt").read_text().strip(),
    "n_overpass_elements": len(osm["elements"]),
    "n_outlets_total": int(len(odf)),
    "n_outlets_shop_lottery": int((odf.shop == "lottery").sum()),
    "n_outlets_operator_pcso": n_pcso_operator,
    "n_outlets_stl": int(odf.is_stl.sum()),
    "n_outlets_in_grid": outlets_in_grid,
    "n_rwi_cells": int(len(rwi)),
    "n_cells_pop": int(len(m)),
    "n_cells_regression": int(len(reg)),
    "national_pop": sig(national_pop),
    "spearman_rho": sig(rho), "spearman_p": sig(pval),
    "per100k_poorer_half": sig(poorer_rate), "per100k_richer_half": sig(richer_rate),
    "ratio_richer_over_poorer": sig(richer_rate / poorer_rate),
    "m1_rwi_irr": sig(m1_irr), "m1_rwi_ci": [sig(c) for c in m1_ci], "m1_rwi_p": sig(m1_p),
    "m2_rwi_irr": sig(m2_irr), "m2_rwi_ci": [sig(c) for c in m2_ci], "m2_rwi_p": sig(m2_p),
    "m2_dens_irr": sig(m2d_irr), "m2_dens_ci": [sig(c) for c in m2d_ci], "m2_dens_p": sig(m2d_p),
}
with open(DERIVED / "headline.json", "w") as fh:
    json.dump(headline, fh, indent=2)
    fh.write("\n")
print("\nHeadline numbers written to data/derived/headline.json")
