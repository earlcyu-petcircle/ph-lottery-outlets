#!/usr/bin/env python3
"""
How uneven is the open outlet record across the country?

Assigns every populated grid cell (by its centre) and every outlet to its GADM province,
using the nearest province for coastal points that fall in the sea, then rolls provinces
up to the 17 administrative regions as they stood before the 2024 Negros Island Region.
Outlets are split into PCSO lotto outlets and Small Town Lottery (STL) points, because
the PCSO's ~4,600 outlet count covers lotto outlets only.

Because most STL points sit in one region, the national wealth model from analysis.py
is re-fitted on lotto outlets alone as a sensitivity check.

Run after analysis.py:  python src/coverage.py
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

from common import DERIVED, RAW, WORK

warnings.filterwarnings("ignore")

REGIONS = {
    "NCR": ["Metropolitan Manila"],
    "CAR": ["Abra", "Apayao", "Benguet", "Ifugao", "Kalinga", "Mountain Province"],
    "I Ilocos": ["Ilocos Norte", "Ilocos Sur", "La Union", "Pangasinan"],
    "II Cagayan Valley": ["Batanes", "Cagayan", "Isabela", "Nueva Vizcaya", "Quirino"],
    "III Central Luzon": ["Aurora", "Bataan", "Bulacan", "Nueva Ecija", "Pampanga", "Tarlac", "Zambales"],
    "IV-A Calabarzon": ["Batangas", "Cavite", "Laguna", "Quezon", "Rizal"],
    "Mimaropa": ["Marinduque", "Occidental Mindoro", "Oriental Mindoro", "Palawan", "Romblon"],
    "V Bicol": ["Albay", "Camarines Norte", "Camarines Sur", "Catanduanes", "Masbate", "Sorsogon"],
    "VI Western Visayas": ["Aklan", "Antique", "Capiz", "Guimaras", "Iloilo", "Negros Occidental"],
    "VII Central Visayas": ["Bohol", "Cebu", "Negros Oriental", "Siquijor"],
    "VIII Eastern Visayas": ["Biliran", "Eastern Samar", "Leyte", "Northern Samar", "Samar", "Southern Leyte"],
    "IX Zamboanga Peninsula": ["Zamboanga del Norte", "Zamboanga del Sur", "Zamboanga Sibugay"],
    "X Northern Mindanao": ["Bukidnon", "Camiguin", "Lanao del Norte", "Misamis Occidental", "Misamis Oriental"],
    "XI Davao": ["Compostela Valley", "Davao del Norte", "Davao del Sur", "Davao Oriental"],
    "XII Soccsksargen": ["North Cotabato", "Sarangani", "South Cotabato", "Sultan Kudarat"],
    "XIII Caraga": ["Agusan del Norte", "Agusan del Sur", "Dinagat Islands", "Surigao del Norte", "Surigao del Sur"],
    "BARMM": ["Basilan", "Lanao del Sur", "Maguindanao", "Sulu", "Tawi-Tawi"],
}
PROVINCE_TO_REGION = {p: r for r, provs in REGIONS.items() for p in provs}
UTM = "EPSG:32651"  # metres, for the nearest-province fallback


def sig(x):
    return float(f"{x:.6g}")


adm1 = gpd.read_file(RAW / "gadm41_PHL.gpkg", layer="ADM_ADM_1")[["NAME_1", "geometry"]]
missing = set(adm1.NAME_1) ^ set(PROVINCE_TO_REGION)
assert not missing, f"province names out of step with GADM: {sorted(missing)}"
adm1["region"] = adm1.NAME_1.map(PROVINCE_TO_REGION)
adm1 = adm1.to_crs(UTM)


def to_region(df, lon, lat):
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(lon, lat), crs=4326).to_crs(UTM)
    joined = gpd.sjoin_nearest(pts, adm1[["region", "geometry"]], how="left")
    return joined[~joined.index.duplicated()]  # a point equidistant from two provinces keeps the first


cells = pd.read_csv(WORK / "analysis_cells.csv")
cells = cells[cells["pop"] > 0]
cells = to_region(cells, (cells.min_lon + cells.max_lon) / 2, (cells.min_lat + cells.max_lat) / 2)
outlets = pd.read_csv(DERIVED / "outlets_clean.csv", keep_default_na=False)
outlets = to_region(outlets, outlets.lon, outlets.lat)

cells["rwi_x_pop"] = cells.rwi * cells["pop"]
reg = cells.groupby("region").agg(population=("pop", "sum"), rwi_x_pop=("rwi_x_pop", "sum"))
reg["mean_rwi"] = reg.rwi_x_pop / reg.population  # population-weighted
counts = outlets.groupby("region").agg(lotto_outlets=("is_stl", lambda s: int((~s).sum())),
                                       stl_points=("is_stl", "sum"))
reg = reg.join(counts).fillna(0).reset_index()
reg[["lotto_outlets", "stl_points"]] = reg[["lotto_outlets", "stl_points"]].astype(int)
reg["lotto_per_100k"] = reg.lotto_outlets / reg.population * 1e5
reg["share_of_population"] = reg.population / reg.population.sum()
reg["share_of_lotto_outlets"] = reg.lotto_outlets / reg.lotto_outlets.sum()
reg = reg.drop(columns="rwi_x_pop").sort_values("mean_rwi", ascending=False)
reg.round({"population": 0, "mean_rwi": 3, "lotto_per_100k": 3,
           "share_of_population": 4, "share_of_lotto_outlets": 4}).to_csv(
    DERIVED / "outlets_by_region.csv", index=False)
print(reg.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

rho, p = spearmanr(reg.mean_rwi, reg.lotto_per_100k)
print(f"\nSpearman(region mean RWI, lotto outlets per 100k) rho={rho:.3f}  p={p:.4f}  (n={len(reg)})")

# Sensitivity: the national model 1 (analysis.py) on lotto outlets only, dropping STL points
lotto = outlets[~outlets.is_stl].groupby(["tx", "ty"]).size().rename("n_lotto")
sub = cells[cells["pop"] >= 50].join(lotto, on=["tx", "ty"])
sub["n_lotto"] = sub["n_lotto"].fillna(0).astype(int)
sub["rwi_z"] = (sub.rwi - sub.rwi.mean()) / sub.rwi.std()
m = smf.glm("n_lotto ~ rwi_z", data=sub, family=sm.families.NegativeBinomial(alpha=1.0),
            offset=np.log(sub["pop"])).fit()
lo, hi = m.conf_int().loc["rwi_z"]
print(f"Model 1 on lotto outlets only: IRR(+1 SD)={math.exp(m.params['rwi_z']):.3f}  "
      f"95% CI=[{math.exp(lo):.3f}, {math.exp(hi):.3f}]  (cells={len(sub):,}, outlets={sub.n_lotto.sum()})")

davao = reg.set_index("region").loc["XI Davao"]
with open(DERIVED / "coverage.json", "w") as fh:
    json.dump({
        "n_lotto_outlets": int(reg.lotto_outlets.sum()), "n_stl_points": int(reg.stl_points.sum()),
        "region_spearman_rho": sig(rho), "region_spearman_p": sig(p),
        "davao_stl_points": int(davao.stl_points), "davao_lotto_outlets": int(davao.lotto_outlets),
        "m1_lotto_only_irr": sig(math.exp(m.params["rwi_z"])),
        "m1_lotto_only_ci": [sig(math.exp(lo)), sig(math.exp(hi))],
        "m1_lotto_only_p": sig(m.pvalues["rwi_z"]),
        "m1_lotto_only_outlets": int(sub.n_lotto.sum()),
    }, fh, indent=2)
    fh.write("\n")
print("Written data/derived/outlets_by_region.csv and data/derived/coverage.json")
