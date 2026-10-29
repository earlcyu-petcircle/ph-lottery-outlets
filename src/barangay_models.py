#!/usr/bin/env python3
"""
National models on barangays and on cities and municipalities (review steps 3-6 and 9).

Outcome: lotto outlets per barangay (the OSM plus Overture union), with a log-population
offset so ratios are rate ratios per person. Exposure: population-weighted quintiles of
barangay wealth (RWI), richest quintile as reference. Controls: PSA urban/rural, log
population density, log mapped retail and food points (OSM plus Overture), log OSM road
length, and province fixed effects. NB2 with an estimated dispersion; a logistic presence
model alongside; Moran's I on the residuals and an eigenvector spatial filter refit.

Robustness: Poisson against NB, with and without commerce, RWI deciles and a continuous
score, lotto-only OSM and STL outside Davao Region, the unit of analysis (tile, barangay,
municipality), PSA municipal poverty when the manual file is present, and a completeness
simulation tied to mapping effort.

Writes data/derived/national_models.json and data/derived/national_quintiles.csv.

Run after barangays.py:  python src/barangay_models.py
"""
import json
import math
import time

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from common import DERIVED, ROOT, WORK, lonlat_to_tile
from countmodels import (QUINTILE_TERMS, add_quintiles, alpha, contiguity, drop_empty_groups,
                         fit_logit, fit_nb2, fit_poisson, morans_i, quintile_rrs, ratio, sig,
                         spatial_filter, zscore)

PCSO_LOTTO_OUTLETS = 4600  # authorised lotto outlets, October 2023 (README reference [4])
Q = " + ".join(QUINTILE_TERMS)
URBANITY = "urban + dens_z"
COMMERCE = "retail_z + road_z"
FE = "C(prov)"
t0 = time.time()


def prepare(df):
    df = df.copy()
    df["logpop"] = np.log(df["pop"])
    df["dens_z"] = zscore(np.log(df["pop"] / df.area_sqkm))
    df["retail_z"] = zscore(np.log1p(df.retail_all))
    df["road_z"] = zscore(np.log1p(df.road_km))
    return df


def pearson_resid(res, df, y):
    mu = res.predict()
    a = res.params.get("alpha", 0.0)
    return (df[y].values - mu) / np.sqrt(mu + a * mu ** 2)


# ---------------------------------------------------------------------------
# 1. Barangay table
# ---------------------------------------------------------------------------
b = pd.read_parquet(WORK / "barangays.parquet")
n_all = len(b)
b = b[(b["pop"] > 0) & b.rwi.notna() & (b.area_sqkm > 0)].copy()
b["urban"] = b.urban.fillna(0.0)  # the few barangays without a census match are rural BARMM areas
b["prov"] = b.adm2_pcode
b["lotto_stl"] = b.lotto_union + b.stl_osm
b = prepare(b)
b = add_quintiles(b, "rwi", "pop")
quint = (b.groupby("quintile").agg(barangays=("rwi", "size"), mean_rwi=("rwi", "mean"),
                                    population=("pop", "sum"), lotto_outlets=("lotto_union", "sum"),
                                    retail_points=("retail_all", "sum"), urban_share=("urban", "mean"))
         .reset_index())
quint["lotto_per_100k"] = quint.lotto_outlets / quint.population * 1e5
quint["retail_per_1k"] = quint.retail_points / quint.population * 1e3
print(f"Barangays in the models: {len(b):,} of {n_all:,}; lotto outlets {int(b.lotto_union.sum())}")
print(quint.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

out = {"n_barangays": int(len(b)), "n_barangays_dropped": int(n_all - len(b)),
       "lotto_outlets": int(b.lotto_union.sum())}

# ---------------------------------------------------------------------------
# 2. Main models: crude, without commerce, with commerce (province fixed effects)
# ---------------------------------------------------------------------------
fe, dropped_prov = drop_empty_groups(b, "lotto_union", "prov")
out["fe_sample"] = {"barangays": int(len(fe)), "provinces": int(fe.prov.nunique()),
                    "provinces_dropped_no_outlets": dropped_prov,
                    "population_share": sig(fe["pop"].sum() / b["pop"].sum())}
off = fe.logpop
m_crude = fit_nb2(f"lotto_union ~ {Q}", b, b.logpop)
m_nocom = fit_nb2(f"lotto_union ~ {Q} + {URBANITY} + {FE}", fe, off)
m_full = fit_nb2(f"lotto_union ~ {Q} + {URBANITY} + {COMMERCE} + {FE}", fe, off)
p_full = fit_poisson(f"lotto_union ~ {Q} + {URBANITY} + {COMMERCE} + {FE}", fe, off)
fe["any_lotto"] = (fe.lotto_union > 0).astype(float)
l_full = fit_logit(f"any_lotto ~ {Q} + logpop + {URBANITY} + {COMMERCE} + {FE}", fe)


def commerce_share(r_without, r_with):
    """Share of the log rate ratio that the commerce controls remove (Rintoul's 40% analogue)."""
    a_, b_ = math.log(r_without["rr"]), math.log(r_with["rr"])
    return sig(1 - b_ / a_) if abs(a_) > 1e-9 else None


out["models"] = {
    "crude": {"quintiles": quintile_rrs(m_crude), "alpha": alpha(m_crude)},
    "no_commerce": {"quintiles": quintile_rrs(m_nocom), "alpha": alpha(m_nocom),
                    "urban": ratio(m_nocom, "urban"), "density": ratio(m_nocom, "dens_z")},
    "full": {"quintiles": quintile_rrs(m_full), "alpha": alpha(m_full),
             "urban": ratio(m_full, "urban"), "density": ratio(m_full, "dens_z"),
             "retail": ratio(m_full, "retail_z"), "roads": ratio(m_full, "road_z")},
    "full_poisson": {"quintiles": quintile_rrs(p_full)},
    "full_presence_logit": {"quintiles": quintile_rrs(l_full)},
}
out["commerce_share_of_q1_gradient"] = commerce_share(out["models"]["no_commerce"]["quintiles"]["q1"],
                                                      out["models"]["full"]["quintiles"]["q1"])
print(f"[{time.time() - t0:.0f}s] main models done; alpha (full) = {alpha(m_full)}")

# ---------------------------------------------------------------------------
# 3. Spatial dependence: Moran's I on residuals, eigenvector spatial filter refit
# ---------------------------------------------------------------------------
adj = contiguity(fe.adm4_pcode.values)
mi = morans_i(pearson_resid(m_full, fe, "lotto_union"), adj)
out["moran_full"] = mi
print(f"[{time.time() - t0:.0f}s] Moran's I on NB residuals: {mi}")
if mi["p_perm"] < 0.05:
    evs = spatial_filter(adj)
    evs.index = fe.index
    fe_sf = fe.join(evs)
    m_sf = fit_nb2(f"lotto_union ~ {Q} + {URBANITY} + {COMMERCE} + {FE} + " + " + ".join(evs.columns),
                   fe_sf, off)
    out["models"]["full_spatial_filter"] = {"quintiles": quintile_rrs(m_sf), "alpha": alpha(m_sf),
                                            "eigenvectors": int(evs.shape[1])}
    out["moran_spatial_filter"] = morans_i(pearson_resid(m_sf, fe_sf, "lotto_union"), adj)
    print(f"[{time.time() - t0:.0f}s] spatial filter with {evs.shape[1]} eigenvectors; "
          f"Moran's I after: {out['moran_spatial_filter']}")

# ---------------------------------------------------------------------------
# 4. Robustness on barangays
# ---------------------------------------------------------------------------
rob = {}
fe = add_quintiles(fe, "rwi", "pop", prefix="d", q=10)
dec = [f"d{k}" for k in range(1, 10)]
r = fit_nb2(f"lotto_union ~ {' + '.join(dec)} + {URBANITY} + {COMMERCE} + {FE}", fe, off)
rob["deciles_full"] = quintile_rrs(r, dec)
fe["rwi_z"] = zscore(fe.rwi)
for name, rhs in [("continuous_no_commerce", f"rwi_z + {URBANITY} + {FE}"),
                  ("continuous_full", f"rwi_z + {URBANITY} + {COMMERCE} + {FE}")]:
    rob[name] = ratio(fit_nb2(f"lotto_union ~ {rhs}", fe, off), "rwi_z")

for outcome, subset in [("lotto_osm", b), ("lotto_stl", b),
                        ("stl_osm", b[~b.adm1_name.str.contains("Region XI")])]:
    s, _ = drop_empty_groups(subset, outcome, "prov")
    rob[f"{outcome}_full"] = {"quintiles": quintile_rrs(
        fit_nb2(f"{outcome} ~ {Q} + {URBANITY} + {COMMERCE} + {FE}", s, s.logpop)),
        "outlets": int(s[outcome].sum()), "barangays": int(len(s))}
rob["stl_osm_full"]["note"] = "STL points outside Davao Region (Region XI)"
out["robustness"] = rob
print(f"[{time.time() - t0:.0f}s] barangay robustness done")

# ---------------------------------------------------------------------------
# 5. Second level: cities and municipalities
# ---------------------------------------------------------------------------
b["rwi_x_pop"] = b.rwi * b["pop"]
b["urban_pop"] = b.urban * b["pop"]
mun = b.groupby(["adm3_pcode", "adm3_name", "adm2_pcode", "adm1_name"], as_index=False).agg(
    pop=("pop", "sum"), area_sqkm=("area_sqkm", "sum"), lotto_union=("lotto_union", "sum"),
    retail_all=("retail_all", "sum"), road_km=("road_km", "sum"), rwi_x_pop=("rwi_x_pop", "sum"),
    urban_pop=("urban_pop", "sum"))
mun["rwi"] = mun.rwi_x_pop / mun["pop"]
mun["urban"] = mun.urban_pop / mun["pop"]  # share of people in urban barangays
mun["prov"] = mun.adm2_pcode
mun = add_quintiles(prepare(mun), "rwi", "pop")
mfe, mdrop = drop_empty_groups(mun, "lotto_union", "prov")
level2 = {"municipalities": int(len(mun)), "fe_sample": int(len(mfe)), "provinces_dropped": mdrop}
level2["rwi_crude"] = {"quintiles": quintile_rrs(fit_nb2(f"lotto_union ~ {Q}", mun, mun.logpop))}
level2["rwi_no_commerce"] = {"quintiles": quintile_rrs(
    fit_nb2(f"lotto_union ~ {Q} + {URBANITY} + {FE}", mfe, mfe.logpop))}
level2["rwi_full"] = {"quintiles": quintile_rrs(
    fit_nb2(f"lotto_union ~ {Q} + {URBANITY} + {COMMERCE} + {FE}", mfe, mfe.logpop))}

psa_file = ROOT / "data" / "manual" / "psa_sae_2021.csv"
if psa_file.exists():
    psa = pd.read_csv(psa_file, dtype={"psgc": str})
    psa["adm3_pcode"] = "PH" + psa.psgc.str.zfill(10).str[:7]
    mp = mun.merge(psa[["adm3_pcode", "poverty_incidence", "cv"]], on="adm3_pcode", how="inner")
    mp["neg_pov"] = -mp.poverty_incidence  # quintile 1 = highest poverty
    mp = add_quintiles(mp, "neg_pov", "pop")
    mpf, _ = drop_empty_groups(mp, "lotto_union", "prov")
    level2["psa_matched"] = int(len(mp))
    level2["psa_rows"] = int(len(psa))
    level2["psa_full"] = {"quintiles": quintile_rrs(
        fit_nb2(f"lotto_union ~ {Q} + {URBANITY} + {COMMERCE} + {FE}", mpf, mpf.logpop))}
    reliable = mpf[mpf.cv < 20]
    level2["psa_full_cv_below_20"] = {"quintiles": quintile_rrs(
        fit_nb2(f"lotto_union ~ {Q} + {URBANITY} + {COMMERCE} + {FE}", reliable, reliable.logpop)),
        "municipalities": int(len(reliable))}
    level2["psa_rwi_spearman"] = sig(mp[["poverty_incidence", "rwi"]].corr("spearman").iloc[0, 1])
else:
    level2["psa"] = "not run: data/manual/psa_sae_2021.csv is missing (docs/psa-poverty-data.md)"
out["municipal"] = level2
print(f"[{time.time() - t0:.0f}s] municipal models done")

# ---------------------------------------------------------------------------
# 6. Units (MAUP): the same crude NB2 on tiles, barangays and municipalities
# ---------------------------------------------------------------------------
cells = pd.read_csv(WORK / "analysis_cells.csv")
cells = cells[cells["pop"] >= 50].copy()
union = pd.read_csv(DERIVED / "outlets_union.csv")
union = union[union["product"] == "lotto"]
utx, uty = lonlat_to_tile(union.lon.values, union.lat.values)
tile_counts = pd.Series(1, index=pd.MultiIndex.from_arrays([utx, uty])).groupby(level=[0, 1]).sum()
cells["lotto_union"] = tile_counts.reindex(pd.MultiIndex.from_arrays([cells.tx, cells.ty])).fillna(0).values
cells["logpop"] = np.log(cells["pop"])
cells = add_quintiles(cells, "rwi", "pop")
units = {}
for name, df in [("tile_2_4km", cells), ("barangay", b), ("municipality", mun)]:
    df = df.copy()
    df["rwi_z"] = zscore(df.rwi)
    units[name] = {"units": int(len(df)), "outlets": int(df.lotto_union.sum()),
                   "quintiles": quintile_rrs(fit_nb2(f"lotto_union ~ {Q}", df, df.logpop)),
                   "per_sd": ratio(fit_nb2("lotto_union ~ rwi_z", df, df.logpop), "rwi_z")}
out["units_crude"] = units
print(f"[{time.time() - t0:.0f}s] unit comparison done")

# ---------------------------------------------------------------------------
# 7. Completeness: how far can missingness tied to mapping effort move the gradient?
#    Mapping effort is a municipality's OSM retail and food points per person. The open
#    record holds about 11% of PCSO's lotto outlets; detection is assumed proportional to
#    effort^gamma, scaled so the expected number detected matches the record.
# ---------------------------------------------------------------------------
osm_ret = b.groupby("adm3_pcode").retail_osm.sum() / b.groupby("adm3_pcode")["pop"].sum()
fe["effort"] = fe.adm3_pcode.map(osm_ret).clip(lower=1e-6)
observed = float(b.lotto_union.sum())
sims, rng = {}, np.random.default_rng(20261029)


def detection(gamma, expected_true):
    raw = fe.effort.values ** gamma
    k = observed / (expected_true * raw).sum()
    for _ in range(50):  # cap at 1 and rescale so the expected total still matches
        p = np.minimum(k * raw, 1.0)
        k *= observed / (expected_true * p).sum()
    return np.minimum(k * raw, 1.0)


share_pop = fe["pop"].values / b["pop"].sum()
true_mean = PCSO_LOTTO_OUTLETS * share_pop
for gamma in (0.5, 1.0):
    p = detection(gamma, true_mean)
    res = {"no_commerce": [], "full": []}
    for _ in range(100):
        fe["y_sim"] = rng.binomial(rng.poisson(true_mean), p)
        s, _ = drop_empty_groups(fe, "y_sim", "prov")
        for key, rhs in [("no_commerce", f"{Q} + {URBANITY} + {FE}"),
                         ("full", f"{Q} + {URBANITY} + {COMMERCE} + {FE}")]:
            res[key].append(math.exp(fit_poisson(f"y_sim ~ {rhs}", s, s.logpop).params["q1"]))
    sims[f"null_gamma_{gamma}"] = {k: {"q1_rr_median": sig(np.median(v)),
                                       "q1_rr_2_5": sig(np.percentile(v, 2.5)),
                                       "q1_rr_97_5": sig(np.percentile(v, 97.5))} for k, v in res.items()}
    # Inverse-probability correction: weight each observed outlet by 1 / detection
    fe["y_ipw"] = fe.lotto_union / p
    sims[f"ipw_gamma_{gamma}"] = {
        key: ratio(smf.glm(f"y_ipw ~ {rhs}", data=fe, family=sm.families.Poisson(),
                           offset=fe.logpop).fit(cov_type="HC1"), "q1")
        for key, rhs in [("no_commerce", f"{Q} + {URBANITY} + {FE}"),
                         ("full", f"{Q} + {URBANITY} + {COMMERCE} + {FE}")]}
out["completeness_simulation"] = sims
print(f"[{time.time() - t0:.0f}s] completeness simulation done")

# ---------------------------------------------------------------------------
# 8. Save
# ---------------------------------------------------------------------------
quint.round({"mean_rwi": 3, "population": 0, "urban_share": 3, "lotto_per_100k": 3,
             "retail_per_1k": 3}).to_csv(DERIVED / "national_quintiles.csv", index=False)
with open(DERIVED / "national_models.json", "w") as fh:
    json.dump(out, fh, indent=2)
    fh.write("\n")
print("Written data/derived/national_models.json and data/derived/national_quintiles.csv")
