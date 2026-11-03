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

Scopes (SCOPES):
  national_tiles      province intercepts, errors clustered by province          (main)
  national_barangays  province intercepts, errors clustered by RWI tile          (check)
  ncr_barangays       city/municipality intercepts, errors clustered by RWI tile (NCR main)
  ncr_tiles           NCR district intercepts, robust errors; only ~120 tiles   (low-n check)

Spatial checks: Moran's I on the residuals of every main count model, on mid-quantile and
deviance residuals. Where either clusters (p < 0.05) the model is refitted with Moran
eigenvector spatial filters (the spatial refit, a frequentist stand-in for BYM2): the smallest
of 10, 25, 50 or up to 100 leading eigenvectors that leaves no significant positive residual
clustering, else the set that leaves the least. That wealth rate ratio is reported too.
A presence model is skipped where fewer than 20 units have, or lack, an outlet (NCR tiles).
Local Moran (LISA) clusters of the main residuals feed the web map's hot-spot layer.

Used by notebooks/02_count_and_presence_models.ipynb and notebooks/03_ncr_zoom_in.ipynb:
fit_scope() fits one scope, fit_sensitivities() the outcome-placement checks, and
write_tables() writes results/tables/models.csv, coefficients.csv and spatial_checks.csv.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

from analysis_samples import BARANGAYS, NCR, RWI_SD, TABLES, TILES
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
PRESENCE = {"+ urban share": ["wealth", "log_pop", "urban_share"],
            "+ shops": ["wealth", "log_pop", "urban_share", "log_shops"]}
EIGENVECTOR_STEPS = (10, 25, 50)  # spatial-refit sizes tried before the full set (at most 100)
MIN_PRESENCE_CASES = 20  # a presence model needs at least this many units with and without an outlet
LISA_SCOPES = ("national_tiles", "ncr_barangays")  # residual hot spots drawn on the web map

_ncr_b = BARANGAYS[BARANGAYS.region_pcode == NCR].reset_index(drop=True)
_ncr_t = TILES[TILES.region_pcode == NCR].reset_index(drop=True)
_ncr_t["tile_id"] = _ncr_t.quadkey
SCOPES = {  # name -> (scope, unit, rows, intercepts, cluster column, role)
    "national_tiles": ("National", "tile", TILES, "province_pcode", "province_pcode", "main"),
    "national_barangays": ("National", "barangay", BARANGAYS, "province_pcode", "main_tile", "check"),
    "ncr_barangays": ("NCR", "barangay", _ncr_b, "adm3_pcode", "main_tile", "NCR main"),
    "ncr_tiles": ("NCR", "tile", _ncr_t, "province_pcode", "tile_id", "low-n check"),
}


def _new_part():
    return {"models": [], "coefs": [], "spatial": []}


def _record(part, key, model, variant, res, df, terms, outcome="outlets", extra=None):
    scope, unit, _, fe, cl, role = SCOPES[key]
    ci = np.exp(res.conf_int().loc["wealth"].to_numpy())
    row = {"scope": scope, "unit": unit, "role": role, "model": model, "variant": variant,
           "outcome": outcome, "controls": " ".join(t for t in terms if t != "wealth"),
           "intercepts": fe, "clustered_by": cl, "n": int(res.nobs), "clusters": int(df[cl].nunique()),
           "outlets": int(df[outcome].sum()) if outcome != "any_outlet" else int(df.outlets.sum()),
           "units_with_outlet": int((df.outlets > 0).sum()),
           "estimate": "rate ratio" if model != "presence" else "odds ratio",
           "wealth_ratio": float(np.exp(res.params["wealth"])), "ci_low": ci[0], "ci_high": ci[1],
           "p_value": float(res.pvalues["wealth"]),
           "nb2_alpha": getattr(res, "nb2_alpha", np.nan), **(extra or {})}
    part["models"].append(row)
    for term in terms:
        lo, hi = res.conf_int().loc[term]
        part["coefs"].append({"scope": scope, "unit": unit, "model": model, "variant": variant, "outcome": outcome,
                              "term": term, "coef": res.params[term], "se": res.bse[term], "ci_low": lo,
                              "ci_high": hi, "exp_coef": np.exp(res.params[term]), "p_value": res.pvalues[term]})
    return row


def spatial_weights(key, df):
    """Neighbours: the 8 surrounding tiles on the RWI grid, or barangays sharing a boundary."""
    if SCOPES[key][1] == "tile":
        return grid_weights(df.tx, df.ty)
    geoms = gpd.read_parquet(WORK / "barangay_geoms.parquet").set_index("adm4_pcode")
    return polygon_weights(geoms.loc[df.adm4_pcode].reset_index())


def _spatial_refit(part, key, df, X, cl, w, variant, terms, eigvecs):
    """The smallest set of leading eigenvectors that leaves no significant positive residual
    clustering; failing that, the set that leaves the least."""
    scope, unit = SCOPES[key][:2]
    if "vecs" not in eigvecs:
        eigvecs["vecs"] = eigenvector_filter(w)[0]
    vecs = eigvecs["vecs"]
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
    r = _record(part, key, "count, spatial refit", variant, sres, df, terms, extra={"eigenvectors": k})
    part["spatial"].append({"scope": scope, "unit": unit, "model": "count, spatial refit", "variant": variant,
                            "residuals": "mid-quantile", **after})
    return r, after


def fit_scope(key, verbose=True):
    """
    Every count variant, the spatial checks and refits, and the presence models for one scope.
    Returns {"models", "coefs", "spatial"} row lists for write_tables(); for the scopes on the
    web map it also writes the main residuals and their LISA clusters to data/work/.
    """
    scope, unit, df, fe, cl, _ = SCOPES[key]
    say = print if verbose else (lambda *a, **k: None)
    say(f"{scope} {unit}s: {len(df):,} units, {int(df.outlets.sum()):,} outlets")
    part, w, eigvecs, residuals = _new_part(), None, {}, None
    for variant, terms in VARIANTS.items():
        X = design(df, terms, fe)
        res = fit_nb2(df.outlets, X, np.log(df["pop"]), df[cl])
        r = _record(part, key, "count", variant, res, df, terms)
        say(f"  count {variant:18s} rate ratio {r['wealth_ratio']:.3f} ({r['ci_low']:.3f}-{r['ci_high']:.3f})")
        if variant not in MAIN:
            continue
        w = spatial_weights(key, df) if w is None else w
        q = nb_mid_quantile_residuals(df.outlets, res.mu, res.nb2_alpha)
        tests = {"mid-quantile": morans_i(q, w), "deviance": morans_i(res.resid_deviance, w)}
        for kind, m in tests.items():
            part["spatial"].append({"scope": scope, "unit": unit, "model": "count", "variant": variant,
                                    "residuals": kind, **m})
        if variant == "+ urban share":
            residuals = pd.DataFrame({"quantile_residual": q, "fitted": res.mu})
        if any(m["p_value"] < 0.05 and m["morans_i"] > 0 for m in tests.values()):
            r, after = _spatial_refit(part, key, df, X, cl, w, variant, terms, eigvecs)
            say(f"  spatial refit ({r['eigenvectors']} eigenvectors) rate ratio {r['wealth_ratio']:.3f} "
                f"({r['ci_low']:.3f}-{r['ci_high']:.3f}); residual Moran's I "
                f"{tests['mid-quantile']['morans_i']:.4f} -> {after['morans_i']:.4f}")
    if min(df.any_outlet.sum(), (1 - df.any_outlet).sum()) < MIN_PRESENCE_CASES:
        say(f"  presence model not estimable: {int(df.any_outlet.sum())} of {len(df)} units have an outlet")
    else:
        for variant, terms in PRESENCE.items():
            d = drop_constant_groups(df, fe, "any_outlet")
            res = fit_logit(d.any_outlet, design(d, terms, fe), d[cl])
            r = _record(part, key, "presence", variant, res, d, terms, outcome="any_outlet",
                        extra={"units_dropped_constant_area": len(df) - len(d)})
            say(f"  presence {variant:15s} odds ratio {r['wealth_ratio']:.3f} ({r['ci_low']:.3f}-{r['ci_high']:.3f})"
                f" [{len(df) - len(d)} units in areas with no variation dropped]")
            if variant == "+ urban share":
                part["spatial"].append({"scope": scope, "unit": unit, "model": "presence", "variant": variant,
                                        "residuals": "mid-quantile",
                                        **morans_i(binary_mid_quantile_residuals(d.any_outlet, res.mu),
                                                   spatial_weights(key, d) if len(d) != len(df) else w)})
    if key in LISA_SCOPES:
        lisa = local_morans(residuals.quantile_residual, w)
        out = pd.concat([df[["quadkey" if unit == "tile" else "adm4_pcode"]], residuals, lisa], axis=1)
        out.to_parquet(WORK / f"residuals_{key}.parquet", index=False)
        say("  LISA clusters:", out.cluster.value_counts().to_dict())
    return part


def fit_sensitivities(verbose=True):
    """The national tile main models with the outcome counted under other placement rules."""
    part = _new_part()
    df = TILES.assign(outlets_plus_town=TILES.outlets + TILES.outlets_address_town)
    for label, outcome in (("GPS points consistent with their address only", "outlets_gps_consistent"),
                           ("adding outlets placed only at a town centre", "outlets_plus_town")):
        for variant in MAIN:
            terms = VARIANTS[variant]
            res = fit_nb2(df[outcome], design(df, terms, "province_pcode"), np.log(df["pop"]), df.province_pcode)
            r = _record(part, "national_tiles", f"count, sensitivity: {label}", variant, res, df, terms,
                        outcome=outcome)
            if verbose:
                print(f"  {label}, {variant}: rate ratio {r['wealth_ratio']:.3f} "
                      f"({r['ci_low']:.3f}-{r['ci_high']:.3f})")
    return part


def save_part(part, name):
    """Keep one notebook's model rows in data/work/ until write_tables() combines them."""
    pd.to_pickle(part, WORK / f"model_rows_{name}.pkl")


def load_part(name):
    path = WORK / f"model_rows_{name}.pkl"
    if not path.exists():
        raise SystemExit(f"missing {path}: run notebooks/02_count_and_presence_models.ipynb first")
    return pd.read_pickle(path)


def write_tables(parts):
    """models.csv, coefficients.csv and spatial_checks.csv from the parts, in the order given."""
    tables = {k: pd.DataFrame([row for p in parts for row in p[k]]) for k in ("models", "coefs", "spatial")}
    tables["models"].insert(0, "wealth_unit", f"1 national tile SD of RWI = {RWI_SD:.4f}")
    tables["models"].to_csv(TABLES / "models.csv", index=False, float_format="%.6g")
    tables["coefs"].to_csv(TABLES / "coefficients.csv", index=False, float_format="%.6g")
    tables["spatial"].to_csv(TABLES / "spatial_checks.csv", index=False, float_format="%.6g")
    return tables


def summary(*parts):
    """The wealth ratio of every model in the parts, rounded for reading."""
    m = pd.DataFrame([row for p in parts for row in p["models"]])
    cols = ["scope", "unit", "model", "variant", "estimate", "n", "wealth_ratio", "ci_low", "ci_high", "p_value"]
    return m[cols].round({"wealth_ratio": 3, "ci_low": 3, "ci_high": 3, "p_value": 4})
