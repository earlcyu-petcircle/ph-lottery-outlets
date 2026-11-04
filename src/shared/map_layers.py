"""
What the web map (src/04_build_map/) and the static maps (notebooks/05_maps.ipynb) share:
tile outlines, the wealth x outlet-rate classes, and the colours, so both show the same thing.

The wealth x outlet-rate class crosses wealth terciles (population-weighted, within the
layer's scope) with three outlet levels: no outlet, an outlet rate at or below the scope's
overall rate, and above it. "w1o2" is the poorest tercile with an above-average outlet rate.
"""
import numpy as np
import pandas as pd
from shapely.geometry import box

import atlas
from analysis_samples import weighted_quintile
from common import Z

# Colours: the Atlas data palette (atlas.py), shared with the web map through docs/map/palette.js,
# which src/04_build_map/write_web_palette.py writes from these
RATE_NONE = atlas.NO_OUTLET  # people but no outlet
RATE = atlas.SEQUENTIAL[1:]  # five classes, light to dark cobalt
RWI = atlas.DIVERGING  # seven steps, poorer pink to richer cobalt
BIV = atlas.BIVARIATE
NO_PEOPLE = atlas.NO_PEOPLE
# Local Moran's I clusters of the model residuals (web map only): cobalt and sky for more outlets
# than modelled, pink and amber for fewer; no teal, so pink never sits beside it
LISA = {"High-High": atlas.CATEGORICAL[0], "High-Low": atlas.CATEGORICAL[5], "Low-Low": atlas.CATEGORICAL[1],
        "Low-High": atlas.CATEGORICAL[2]}


def tile_xy(quadkeys):
    """Tile indices (tx, ty) from zoom-14 Bing quadkeys."""
    tx = np.array([int("".join(str(int(c) & 1) for c in q), 2) for q in quadkeys])
    ty = np.array([int("".join(str(int(c) >> 1) for c in q), 2) for q in quadkeys])
    return tx, ty


def tile_polygons(quadkeys, z=Z):
    """The square outline of each RWI tile, in lon/lat."""
    tx, ty = tile_xy(quadkeys)
    n = 2 ** z
    lon_w, lon_e = tx / n * 360 - 180, (tx + 1) / n * 360 - 180
    lat_n = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * ty / n))))
    lat_s = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (ty + 1) / n))))
    return [box(*b) for b in zip(lon_w, lat_s, lon_e, lat_n)]


def map_classes(df):
    """Adds rate_per_100k, the wealth quintile and the wealth x outlet-rate class ("w1o2");
    returns the frame and the scope's overall outlet rate per 100,000."""
    has = df["pop"] > 0
    df["rate_per_100k"] = (df.outlets / df["pop"] * 1e5).where(has)
    df["quintile"] = pd.NA
    df["bivariate"] = pd.NA
    d = df[has & df.rwi.notna()]
    q = weighted_quintile(d.rwi.to_numpy(), d["pop"].to_numpy())
    terc = np.minimum(((np.cumsum(d["pop"].to_numpy()[np.argsort(d.rwi.to_numpy(), kind="stable")])
                        / d["pop"].sum() * 3 - 1e-9).astype(int) + 1), 3)
    tercile = np.empty(len(d), dtype=int)
    tercile[np.argsort(d.rwi.to_numpy(), kind="stable")] = terc
    overall = d.outlets.sum() / d["pop"].sum() * 1e5
    level = np.where(d.outlets == 0, 0, np.where(d.rate_per_100k <= overall, 1, 2))
    df.loc[d.index, "quintile"] = q
    df.loc[d.index, "bivariate"] = [f"w{t}o{lv}" for t, lv in zip(tercile, level)]
    return df, overall
