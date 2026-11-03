"""
The analysis samples shared by every step 3 script, read from the committed step 2 tables.

Wealth enters every model as the Relative Wealth Index (RWI) in units of one national
standard deviation (SD) of tile RWI, measured over populated tiles. The same unit is used for
tiles and barangays, nationally and in each city, so every wealth rate ratio is per the same
change in wealth and the columns of a results table can be read side by side.

The three cities of RQ3 (CITIES) are the `metro` areas of the step 2 tables, defined in
src/shared/common.py: Metro Manila (NCR), Metro Cebu and Metro Davao.
"""
import numpy as np
import pandas as pd

from common import DERIVED, ROOT, lonlat_to_tile

RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
for _d in (TABLES, FIGURES):
    _d.mkdir(parents=True, exist_ok=True)

NCR = "PH13"
CITIES = {"NCR": "Metro Manila", "Metro Cebu": "Metro Cebu", "Metro Davao": "Metro Davao"}  # scope -> metro


def _controls(df):
    df["log_shops"] = np.log1p(df.shops)
    df["log_road_km"] = np.log1p(df.road_km)
    df["log_pop"] = np.log(df["pop"])
    df["any_outlet"] = (df.outlets > 0).astype(int)
    return df


def load_tiles():
    """Every RWI tile with people (the 87 empty tiles cannot carry a per-person rate)."""
    t = pd.read_csv(DERIVED / "tiles.csv", dtype={"quadkey": str})
    t = t[t["pop"] > 0].reset_index(drop=True)
    t["tx"], t["ty"] = lonlat_to_tile(t.lon.to_numpy(), t.lat.to_numpy())
    return _controls(t)


TILES = load_tiles()
RWI_MEAN = float(TILES.rwi.mean())
RWI_SD = float(TILES.rwi.std())


def wealth(rwi):
    """RWI in national tile SDs, centred on the national tile mean."""
    return (rwi - RWI_MEAN) / RWI_SD


TILES["wealth"] = wealth(TILES.rwi)


def load_barangays():
    """Barangays with people and an RWI value (112 barangays, 78,000 people, have none)."""
    b = pd.read_csv(DERIVED / "barangays.csv", dtype={"main_tile": str})
    b = b[(b["pop"] > 0) & b.rwi.notna()].reset_index(drop=True)
    b = _controls(b)
    b["wealth"] = wealth(b.rwi)
    return b


BARANGAYS = load_barangays()


def city(df, scope):
    """The rows of one city scope ("NCR", "Metro Cebu" or "Metro Davao")."""
    return df[df.metro == CITIES[scope]].reset_index(drop=True)


def weighted_quintile(values, weights):
    """Quintile 1 (poorest) to 5 (richest), each holding a fifth of the people."""
    order = np.argsort(values, kind="stable")
    cum = np.cumsum(np.asarray(weights, dtype=float)[order])
    q = np.empty(len(values), dtype=int)
    q[order] = np.minimum((cum / cum[-1] * 5 - 1e-9).astype(int) + 1, 5)
    return q
