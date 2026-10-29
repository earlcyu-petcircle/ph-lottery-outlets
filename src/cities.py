#!/usr/bin/env python3
"""
The headline design while the outcome is OpenStreetMap (review step 7).

Restricts the study to the three city areas where open mapping is densest - Metro Manila
(NCR), Metro Cebu and Davao City - and models lotto outlets as a share of all mapped retail:
a negative-binomial count of OSM lotto outlets with offset log(OSM retail and food points),
log population as a covariate, wealth quintiles within the three areas and area fixed
effects. If mappers record lotto outlets at about the same rate as other shops in a
barangay, mapping effort cancels out of this ratio (Gilliland and Ross's adoption idea).

Also writes the proposed Street View audit sample: 30 barangays, six per wealth quintile,
with empty columns for the audit counts. No audit has been done; the counts are a TODO.

Writes data/derived/cities_models.json, data/derived/cities_mapping.csv,
data/derived/cities_quintiles.csv and data/derived/audit_sample.csv.

Run after barangays.py:  python src/cities.py
"""
import json

import numpy as np
import pandas as pd

from common import DERIVED, METRO_CEBU, WORK, area_of
from countmodels import (QUINTILE_TERMS, add_quintiles, alpha, contiguity, fit_logit, fit_nb2,
                         morans_i, quintile_rrs, ratio, sig, spatial_filter, zscore)

PCSO_PER_100K = 4.2  # about 4,600 authorised lotto outlets against 109.6 million people
Q = " + ".join(QUINTILE_TERMS)


def pearson_resid(res, y):
    mu = res.predict()
    return (y - mu) / np.sqrt(mu + res.params["alpha"] * mu ** 2)


b = pd.read_parquet(WORK / "barangays.parquet")
b["area"] = area_of(b)
assert b.loc[b.area == "Metro Cebu", "adm3_name"].nunique() == len(METRO_CEBU)

# ---------------------------------------------------------------------------
# 1. How well mapped is each area? (the case for restricting to these three)
# ---------------------------------------------------------------------------
mp = b.groupby("area").agg(barangays=("pop", "size"), population=("pop", "sum"),
                           area_km2=("area_sqkm", "sum"), osm_retail=("retail_osm", "sum"),
                           overture_retail=("retail_overture", "sum"), road_km=("road_km", "sum"),
                           osm_lotto=("lotto_osm", "sum"), union_lotto=("lotto_union", "sum"))
mp["osm_retail_per_1k"] = mp.osm_retail / mp.population * 1e3
mp["overture_retail_per_1k"] = mp.overture_retail / mp.population * 1e3
mp["road_km_per_km2"] = mp.road_km / mp.area_km2
mp["union_lotto_per_100k"] = mp.union_lotto / mp.population * 1e5
mp["share_of_pcso_average"] = mp.union_lotto_per_100k / PCSO_PER_100K
mp["osm_lotto_per_100_osm_retail"] = mp.osm_lotto / mp.osm_retail * 100
order = ["Metro Manila (NCR)", "Metro Cebu", "Davao City", "Rest of the country"]
mp = mp.loc[order].reset_index()
mp.round(3).to_csv(DERIVED / "cities_mapping.csv", index=False)
print(mp.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

# ---------------------------------------------------------------------------
# 2. The restricted sample and within-area wealth quintiles
# ---------------------------------------------------------------------------
s = b[(b.area != "Rest of the country") & (b["pop"] > 0) & b.rwi.notna()].copy()
s["logpop"] = np.log(s["pop"])
s["logpop_z"] = zscore(s.logpop)
s["dens_z"] = zscore(np.log(s["pop"] / s.area_sqkm))
s["retail_z"] = zscore(np.log1p(s.retail_all))
s["road_z"] = zscore(np.log1p(s.road_km))
s = add_quintiles(s, "rwi", "pop")
qt = s.groupby("quintile").agg(barangays=("pop", "size"), mean_rwi=("rwi", "mean"),
                               population=("pop", "sum"), osm_retail=("retail_osm", "sum"),
                               osm_lotto=("lotto_osm", "sum"), union_lotto=("lotto_union", "sum"))
qt["osm_lotto_per_100_osm_retail"] = qt.osm_lotto / qt.osm_retail * 100
qt["osm_retail_per_1k"] = qt.osm_retail / qt.population * 1e3
qt["union_lotto_per_100k"] = qt.union_lotto / qt.population * 1e5
qt = qt.reset_index()
qt.round(3).to_csv(DERIVED / "cities_quintiles.csv", index=False)
print(qt.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

# ---------------------------------------------------------------------------
# 3. Mapped-share model (headline) and the per-person models in the same cities
# ---------------------------------------------------------------------------
sh = s[s.retail_osm > 0].copy()
share = fit_nb2(f"lotto_osm ~ {Q} + logpop_z + dens_z + C(area)", sh, np.log(sh.retail_osm))
sh_u = s[s.retail_all > 0].copy()
share_u = fit_nb2(f"lotto_union ~ {Q} + logpop_z + dens_z + C(area)", sh_u, np.log(sh_u.retail_all))
pc_nocom = fit_nb2(f"lotto_union ~ {Q} + dens_z + C(area)", s, s.logpop)
pc_full = fit_nb2(f"lotto_union ~ {Q} + dens_z + retail_z + road_z + C(area)", s, s.logpop)
# Metro Cebu's mapping density is close to the national rest (section 1), so drop it as a check
sh2 = sh[sh.area != "Metro Cebu"]
share_2 = fit_nb2(f"lotto_osm ~ {Q} + logpop_z + dens_z + C(area)", sh2, np.log(sh2.retail_osm))
s["any_lotto"] = (s.lotto_union > 0).astype(float)
presence = fit_logit(f"any_lotto ~ {Q} + logpop + dens_z + retail_z + road_z + C(area)", s)

out = {
    "n_barangays": int(len(s)), "population": sig(s["pop"].sum()),
    "osm_lotto": int(s.lotto_osm.sum()), "union_lotto": int(s.lotto_union.sum()),
    "osm_retail": int(s.retail_osm.sum()),
    "share_sample_barangays": int(len(sh)), "share_sample_osm_lotto": int(sh.lotto_osm.sum()),
    "share_sample_pop_share": sig(sh["pop"].sum() / s["pop"].sum()),
    "models": {
        "share_osm": {"quintiles": quintile_rrs(share), "alpha": alpha(share),
                      "logpop": ratio(share, "logpop_z"), "density": ratio(share, "dens_z")},
        "share_union": {"quintiles": quintile_rrs(share_u), "alpha": alpha(share_u)},
        "share_osm_ncr_davao_only": {"quintiles": quintile_rrs(share_2), "alpha": alpha(share_2),
                                     "barangays": int(len(sh2)), "osm_lotto": int(sh2.lotto_osm.sum())},
        "per_person_no_commerce": {"quintiles": quintile_rrs(pc_nocom), "alpha": alpha(pc_nocom)},
        "per_person_full": {"quintiles": quintile_rrs(pc_full), "alpha": alpha(pc_full)},
        "presence_logit": {"quintiles": quintile_rrs(presence)},
    },
}
adj = contiguity(sh.adm4_pcode.values)
out["moran_share_osm"] = morans_i(pearson_resid(share, sh.lotto_osm.values), adj)
if out["moran_share_osm"]["p_perm"] < 0.05:
    evs = spatial_filter(adj, k=30)
    evs.index = sh.index
    shf = sh.join(evs)
    m = fit_nb2(f"lotto_osm ~ {Q} + logpop_z + dens_z + C(area) + " + " + ".join(evs.columns),
                shf, np.log(shf.retail_osm))
    out["models"]["share_osm_spatial_filter"] = {"quintiles": quintile_rrs(m), "eigenvectors": int(evs.shape[1])}
    out["moran_share_osm_spatial_filter"] = morans_i(pearson_resid(m, shf.lotto_osm.values), adj)
print(json.dumps(out, indent=1))
with open(DERIVED / "cities_models.json", "w") as fh:
    json.dump(out, fh, indent=2)
    fh.write("\n")

# ---------------------------------------------------------------------------
# 4. Proposed audit sample (TODO): six barangays per within-city wealth quintile
# ---------------------------------------------------------------------------
rng = np.random.default_rng(20261029)
eligible = s[s.retail_osm > 0]
pick = pd.concat([g.loc[rng.choice(g.index, 6, replace=False)]
                  for _, g in eligible.groupby("quintile", sort=True)])
audit = pick[["adm4_pcode", "adm4_name", "adm3_name", "area", "quintile", "pop", "retail_osm",
              "lotto_osm", "lotto_union"]].rename(columns={"pop": "population"})
audit["population"] = audit.population.round(0).astype(int)
audit["audited_lotto_outlets"] = ""   # TODO: Street View or walk count; not done
audit["audited_retail_points"] = ""   # TODO
audit["audit_date"] = ""
audit.sort_values(["area", "quintile", "adm4_pcode"]).to_csv(DERIVED / "audit_sample.csv", index=False)
print("Written data/derived/cities_*.{json,csv} and data/derived/audit_sample.csv")
