#!/usr/bin/env python3
"""
One outlet table from both open sources: OpenStreetMap and Overture Maps.

OSM outlets are the cleaned list from analysis.py (lotto and Small Town Lottery kept apart).
Overture places are classified by name and category with the rules of the earlier Overture
scout: lotto outlets are kept, PCSO offices, results pages and name false positives are
dropped, and STL-named places are left out because they are mostly operator offices rather
than betting points. An Overture outlet joins the union only if it is more than 100 m from
every OSM outlet, so the two sources are not double counted.

Writes data/derived/outlets_union.csv (no names: Overture names include personal names).

Run after analysis.py:  python src/outlets.py
"""
import json
import re

import geopandas as gpd
import numpy as np
import pandas as pd

from common import DERIVED, RAW

UTM = "EPSG:32651"
WIDE = re.compile(r"lotto|pcso|sweepstake|small town lottery|\bstl\b|lotter|lottohan|ez2|swertres", re.I)
LOTTO = re.compile(r"\blotto|lottohan|\blottery\b", re.I)
NOT_PH = re.compile(r"texas|powerball|mega millions|picks|tips", re.I)  # foreign or tipster pages
OFFICE = re.compile(r"branch|office|regional|district|warehouse|clinic|fund|result|assistance|"
                    r"finance|charity sweepstakes|\btips?\b|predict", re.I)
BARE_PCSO = re.compile(r"^\s*pcso\b(?!.*lotto)", re.I)
STORE = re.compile(r"store|mart|grocery|supermarket|savemore|puregold|sari|station|pharmacy|"
                   r"merchandis|trading|enterprise|convenience", re.I)


def overture_class(name, category, alts):
    name = name or ""
    is_vendor = category == "lottery_vendor" or "lottery_vendor" in list(alts if alts is not None else [])
    if not (is_vendor or WIDE.search(name)):
        return None
    if OFFICE.search(name) or BARE_PCSO.search(name) or NOT_PH.search(name):
        return "office_or_noise"
    if LOTTO.search(name):
        return "lotto"
    if re.search(r"\bstl\b|small town lottery", name, re.I):
        return "stl_operator"
    if is_vendor and STORE.search(name):
        return "lotto"  # a terminal inside another shop, filed under lottery_vendor
    return "false_positive"


osm = pd.read_csv(DERIVED / "outlets_clean.csv", keep_default_na=False)
osm = pd.DataFrame({"source": "osm", "id": osm.osm_type + "/" + osm.osm_id.astype(str),
                    "product": np.where(osm.is_stl, "stl", "lotto"), "lon": osm.lon, "lat": osm.lat})

ov = pd.read_parquet(RAW / "overture_places_ph.parquet",
                     columns=["id", "lon", "lat", "name", "category", "alt_categories", "country"])
ov = ov[ov.country == "PH"]
ov["cls"] = [overture_class(n, c, a) for n, c, a in zip(ov.name, ov.category, ov.alt_categories)]
counts = ov.cls.value_counts().to_dict()
ovl = ov[ov.cls == "lotto"]

g_osm = gpd.GeoDataFrame(osm, geometry=gpd.points_from_xy(osm.lon, osm.lat), crs=4326).to_crs(UTM)
g_ov = gpd.GeoDataFrame(ovl[["id", "lon", "lat"]], geometry=gpd.points_from_xy(ovl.lon, ovl.lat),
                        crs=4326).to_crs(UTM)
near = gpd.sjoin_nearest(g_ov, g_osm[["geometry"]], how="left", distance_col="d_osm")
near = near[~near.index.duplicated()]
new = near[near.d_osm > 100]
ov_out = pd.DataFrame({"source": "overture", "id": new.id, "product": "lotto",
                       "lon": new.lon, "lat": new.lat})
union = pd.concat([osm, ov_out], ignore_index=True)
union.round({"lon": 6, "lat": 6}).to_csv(DERIVED / "outlets_union.csv", index=False)

summary = {
    "overture_candidates": {k: int(v) for k, v in counts.items()},
    "overture_lotto": int(len(ovl)),
    "overture_lotto_within_100m_of_osm": int((near.d_osm <= 100).sum()),
    "union_lotto": int((union["product"] == "lotto").sum()),
    "union_stl": int((union["product"] == "stl").sum()),
}
with open(DERIVED / "outlets_union.json", "w") as fh:
    json.dump(summary, fh, indent=2)
    fh.write("\n")
print(json.dumps(summary, indent=2))
