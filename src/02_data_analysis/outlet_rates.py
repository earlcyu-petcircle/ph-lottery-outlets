"""
Descriptive tables: outlets per 100,000 people by wealth quintile, and how outlets and people
are spread over tiles and barangays, nationally and in the National Capital Region (NCR).

Quintiles are population-weighted (each holds a fifth of the people in its scope), so NCR's
quintiles split NCR's own people and say how its poorer and richer parts compare with each
other. A quintile row describes where outlets are; it does not adjust for anything.

Used by notebooks/01_descriptives.ipynb.
"""
import numpy as np
import pandas as pd

from analysis_samples import BARANGAYS, NCR, TILES, weighted_quintile


def scopes():
    """(scope, unit, rows) for every view the descriptive tables cover."""
    return [
        ("National", "tile", TILES),
        ("National", "barangay", BARANGAYS),
        ("NCR", "barangay", BARANGAYS[BARANGAYS.region_pcode == NCR]),
        ("NCR", "tile", TILES[TILES.region_pcode == NCR]),
    ]


def quintile_rates():
    """One row per scope, unit and quintile (plus "All"): people, outlets and rates."""
    rows = []
    for scope, unit, df in scopes():
        df = df.copy()
        df["quintile"] = weighted_quintile(df.rwi.to_numpy(), df["pop"].to_numpy())
        for q, g in [*df.groupby("quintile"), ("All", df)]:
            rows.append({
                "scope": scope, "unit": unit, "quintile": q, "units": len(g),
                "rwi_min": g.rwi.min(), "rwi_max": g.rwi.max(),
                "rwi_mean_pop_weighted": np.average(g.rwi, weights=g["pop"]),
                "pop": g["pop"].sum(), "outlets": int(g.outlets.sum()),
                "outlets_per_100k": g.outlets.sum() / g["pop"].sum() * 1e5,
                "share_units_no_outlet": (g.outlets == 0).mean(),
                "share_people_in_units_no_outlet": g.loc[g.outlets == 0, "pop"].sum() / g["pop"].sum(),
                "shops_per_1k": g.shops.sum() / g["pop"].sum() * 1e3,
                "urban_share_people": np.average(g.urban_share.fillna(0), weights=g["pop"]),
            })
    return pd.DataFrame(rows)


def distribution():
    """Distribution summaries of outlets, people, outlet rate, RWI and shops per unit."""
    rows = []
    for scope, unit, df in scopes():
        rate = df.outlets / df["pop"] * 1e5
        for var, s in (("outlets", df.outlets), ("pop", df["pop"]), ("outlets_per_100k", rate),
                       ("rwi", df.rwi), ("shops", df.shops)):
            rows.append({"scope": scope, "unit": unit, "variable": var, "units": len(s), "mean": s.mean(),
                         "sd": s.std(), "min": s.min(), "p25": s.quantile(.25), "median": s.median(),
                         "p75": s.quantile(.75), "p90": s.quantile(.9), "p99": s.quantile(.99), "max": s.max(),
                         "share_zero": (s == 0).mean()})
    return pd.DataFrame(rows)
