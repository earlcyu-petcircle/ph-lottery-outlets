#!/usr/bin/env python3
"""
Count and presence models of the association between wealth and PCSO lotto outlet density.

Each count model is an NB2 negative binomial with estimated dispersion: outlets per unit, the
log of the unit's people as the offset (so it compares outlets per person), area intercepts,
and wealth as the RWI in national tile SDs. exp(wealth coefficient) is the wealth rate ratio:
how many times as many outlets per person a unit one SD richer has, holding the other terms
fixed. Above 1, richer places have more outlets per person; below 1, poorer places do. It
describes where outlets are relative to wealth and says nothing about why they are there.

Variants, each with and without commerce:
  wealth only          wealth + area intercepts
  + urban share        + GHSL urban share                     (main model without shops)
  + shops              + log(1 + OSM and Overture shops)      (main model with shops)
  + shops and roads    + log(1 + OSM road km)
The presence model is a logit of "any outlet" on wealth, log people and the same controls;
exp(wealth coefficient) is an odds ratio.

Scopes:
  National tiles      province intercepts, errors clustered by province          (main)
  National barangays  province intercepts, errors clustered by RWI tile          (check)
  NCR barangays       city/municipality intercepts, errors clustered by RWI tile (NCR main)
  NCR tiles           NCR district intercepts, robust errors; only ~120 tiles   (low-n check)

Spatial checks: Moran's I on the residuals of every main count model, on mid-quantile and
deviance residuals. Where either clusters (p < 0.05) the model is refitted with Moran
eigenvector spatial filters (the spatial refit, a frequentist stand-in for BYM2): the smallest
of 10, 25, 50 or up to 100 leading eigenvectors that leaves no significant positive residual
clustering, else the set that leaves the least. That wealth rate ratio is reported too.
A presence model is skipped where fewer than 20 units have, or lack, an outlet (NCR tiles).
Local Moran (LISA) clusters of the main residuals feed the web map's hot-spot layer.

Writes results/tables/models.csv (one row per model), coefficients.csv, spatial_checks.csv,
and data/work/residuals_tiles.parquet, residuals_ncr_barangays.parquet for the web map.

Run after tables.py:  python src/models.py
"""
import geopandas as gpd
import numpy as np
import pandas as pd

from analysis_data import BARANGAYS, NCR, RWI_SD, TABLES, TILES
from common import WORK
from stats_tools import (binary_mid_quantile_residuals, design, drop_constant_groups, eigenvector_filter,
                         fit_logit, fit_nb2, grid_weights, local_morans, morans_i, nb_mid_quantile_residuals,
                         polygon_weights)

VARIANTS = {
    "wealth only": ["wealth"],
    "+ urban share": ["wealth", "urban_share"],
    "+ shops": ["wealth", "urban_share", "log_shops"],
    "+ shops and roads": ["wealth", "urban_share", "log_shops", "log_road_km"],
}
MAIN = ("+ urban share", "+ shops")  # the pair reported as "without" and "with" the shops control
EIGENVECTOR_STEPS = (10, 25, 50)  # spatial-refit sizes tried before the full set (at most 100)
MIN_PRESENCE_CASES = 20  # a presence model needs at least this many units with and without an outlet
eigvecs = {}
PRESENCE = {"+ urban share": ["wealth", "log_pop", "urban_share"],
            "+ shops": ["wealth", "log_pop", "urban_share", "log_shops"]}

ncr_b = BARANGAYS[BARANGAYS.region_pcode == NCR].reset_index(drop=True)
ncr_t = TILES[TILES.region_pcode == NCR].reset_index(drop=True)
TILES["tile_id"] = TILES.quadkey
ncr_t["tile_id"] = ncr_t.quadkey
SCOPES = {  # name -> (scope, unit, rows, intercepts, cluster column, note)
    "national_tiles": ("National", "tile", TILES, "province_pcode", "province_pcode", "main"),
    "national_barangays": ("National", "barangay", BARANGAYS, "province_pcode", "main_tile", "check"),
    "ncr_barangays": ("NCR", "barangay", ncr_b, "adm3_pcode", "main_tile", "NCR main"),
    "ncr_tiles": ("NCR", "tile", ncr_t, "province_pcode", "tile_id", "low-n check"),
}

models, coefs, spatial = [], [], []


def record(key, model, variant, res, df, terms, outcome="outlets", extra=None):
    scope, unit, _, fe, cl, note = SCOPES[key]
    ci = np.exp(res.conf_int().loc["wealth"].to_numpy())
    row = {"scope": scope, "unit": unit, "role": note, "model": model, "variant": variant,
           "outcome": outcome, "controls": " ".join(t for t in terms if t != "wealth"),
           "intercepts": fe, "clustered_by": cl, "n": int(res.nobs), "clusters": int(df[cl].nunique()),
           "outlets": int(df[outcome].sum()) if outcome != "any_outlet" else int(df.outlets.sum()),
           "units_with_outlet": int((df.outlets > 0).sum()),
           "estimate": "rate ratio" if model != "presence" else "odds ratio",
           "wealth_ratio": float(np.exp(res.params["wealth"])), "ci_low": ci[0], "ci_high": ci[1],
           "p_value": float(res.pvalues["wealth"]),
           "nb2_alpha": getattr(res, "nb2_alpha", np.nan), **(extra or {})}
    models.append(row)
    for term in terms:
        lo, hi = res.conf_int().loc[term]
        coefs.append({"scope": scope, "unit": unit, "model": model, "variant": variant, "outcome": outcome,
                      "term": term, "coef": res.params[term], "se": res.bse[term], "ci_low": lo, "ci_high": hi,
                      "exp_coef": np.exp(res.params[term]), "p_value": res.pvalues[term]})
    return row


def weights_for(key, df):
    if SCOPES[key][1] == "tile":
        return grid_weights(df.tx, df.ty)
    geoms = gpd.read_parquet(WORK / "barangay_geoms.parquet").set_index("adm4_pcode")
    return polygon_weights(geoms.loc[df.adm4_pcode].reset_index())


residual_maps = {}
for key, (scope, unit, df, fe, cl, note) in SCOPES.items():
    print(f"== {scope} {unit}s: {len(df):,} units, {int(df.outlets.sum()):,} outlets", flush=True)
    w = None
    for variant, terms in VARIANTS.items():
        X = design(df, terms, fe)
        res = fit_nb2(df.outlets, X, np.log(df["pop"]), df[cl])
        r = record(key, "count", variant, res, df, terms)
        print(f"   count {variant:18s} RR {r['wealth_ratio']:.3f} ({r['ci_low']:.3f}-{r['ci_high']:.3f})", flush=True)
        if variant not in MAIN:
            continue
        # Spatial check on the main count models
        w = weights_for(key, df) if w is None else w
        q = nb_mid_quantile_residuals(df.outlets, res.mu, res.nb2_alpha)
        tests = {"mid-quantile": morans_i(q, w), "deviance": morans_i(res.resid_deviance, w)}
        for kind, m in tests.items():
            spatial.append({"scope": scope, "unit": unit, "model": "count", "variant": variant,
                            "residuals": kind, **m})
        if variant == "+ urban share":
            residual_maps[key] = pd.DataFrame({"quantile_residual": q, "fitted": res.mu})
        clusters = any(m["p_value"] < 0.05 and m["morans_i"] > 0 for m in tests.values())
        if clusters:
            # The smallest set of leading eigenvectors that leaves no significant positive
            # residual clustering; failing that, the set that leaves the least.
            vecs = eigenvector_filter(w)[0] if key not in eigvecs else eigvecs[key]
            eigvecs[key] = vecs
            best = None
            for k in [k for k in EIGENVECTOR_STEPS if k < vecs.shape[1]] + [vecs.shape[1]]:
                ev = pd.DataFrame(vecs[:, :k], columns=[f"ev{i}" for i in range(k)], index=df.index)
                sres = fit_nb2(df.outlets, pd.concat([X, ev], axis=1), np.log(df["pop"]), df[cl])
                after = morans_i(nb_mid_quantile_residuals(df.outlets, sres.mu, sres.nb2_alpha), w)
                if best is None or after["morans_i"] < best[2]["morans_i"]:
                    best = (k, sres, after)
                if after["p_value"] >= 0.05 or after["morans_i"] <= 0:
                    best = (k, sres, after)
                    break
            k, sres, after = best
            r = record(key, "count, spatial refit", variant, sres, df, terms, extra={"eigenvectors": k})
            spatial.append({"scope": scope, "unit": unit, "model": "count, spatial refit", "variant": variant,
                            "residuals": "mid-quantile", **after})
            print(f"   spatial refit ({k} eigenvectors) RR {r['wealth_ratio']:.3f} "
                  f"({r['ci_low']:.3f}-{r['ci_high']:.3f}); residual Moran's I {tests['mid-quantile']['morans_i']:.4f}"
                  f" -> {after['morans_i']:.4f}", flush=True)
    if min(df.any_outlet.sum(), (1 - df.any_outlet).sum()) < MIN_PRESENCE_CASES:
        print(f"   presence model not estimable: {int(df.any_outlet.sum())} of {len(df)} units have an outlet")
        continue
    for variant, terms in PRESENCE.items():
        d = drop_constant_groups(df, fe, "any_outlet")
        res = fit_logit(d.any_outlet, design(d, terms, fe), d[cl])
        r = record(key, "presence", variant, res, d, terms, outcome="any_outlet",
                   extra={"units_dropped_constant_area": len(df) - len(d)})
        print(f"   presence {variant:15s} OR {r['wealth_ratio']:.3f} ({r['ci_low']:.3f}-{r['ci_high']:.3f})"
              f" [{len(df) - len(d)} units in areas with no variation dropped]", flush=True)
        if key in residual_maps and variant == "+ urban share":
            spatial.append({"scope": scope, "unit": unit, "model": "presence", "variant": variant,
                            "residuals": "mid-quantile",
                            **morans_i(binary_mid_quantile_residuals(d.any_outlet, res.mu),
                                       weights_for(key, d) if len(d) != len(df) else w)})
    if key in ("national_tiles", "ncr_barangays"):
        lisa = local_morans(residual_maps[key].quantile_residual, w)
        out = pd.concat([df[["quadkey" if unit == "tile" else "adm4_pcode"]], residual_maps[key], lisa], axis=1)
        out.to_parquet(WORK / f"residuals_{key}.parquet", index=False)
        print("   LISA clusters:", out.cluster.value_counts().to_dict(), flush=True)

# Sensitivities on the national tile main models: placement rules for the outcome
for label, outcome in (("GPS points consistent with their address only", "outlets_gps_consistent"),
                       ("adding outlets placed only at a town centre", "outlets_plus_town")):
    df = TILES.assign(outlets_plus_town=TILES.outlets + TILES.outlets_address_town)
    for variant in MAIN:
        terms = VARIANTS[variant]
        res = fit_nb2(df[outcome], design(df, terms, "province_pcode"), np.log(df["pop"]), df.province_pcode)
        r = record("national_tiles", f"count, sensitivity: {label}", variant, res, df, terms, outcome=outcome)
        print(f"   sensitivity {outcome} {variant}: RR {r['wealth_ratio']:.3f} ({r['ci_low']:.3f}-{r['ci_high']:.3f})")

m = pd.DataFrame(models)
m.insert(0, "wealth_unit", f"1 national tile SD of RWI = {RWI_SD:.4f}")
m.to_csv(TABLES / "models.csv", index=False, float_format="%.6g")
pd.DataFrame(coefs).to_csv(TABLES / "coefficients.csv", index=False, float_format="%.6g")
pd.DataFrame(spatial).to_csv(TABLES / "spatial_checks.csv", index=False, float_format="%.6g")
print(f"models.csv: {len(m)} models; wealth unit: 1 SD = {RWI_SD:.4f} RWI points")
