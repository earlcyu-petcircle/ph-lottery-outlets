#!/usr/bin/env python3
"""
Build the two analysis-ready tables and the data-quality tables behind docs/data-quality.md.

  data/derived/tiles.csv      one row per Meta RWI tile (zoom 14, about 2.4 km): the main unit
  data/derived/barangays.csv  one row per COD-AB barangay: the check

Both carry PCSO outlets, people (2020 census counts spread over WorldPop 2024 100 m pixels),
RWI and its error, OSM and Overture shop and food points, OSM road length, urban share,
province, region, PCSO area and the three city areas. No outlet-level rows are written.

Also writes data/derived/quality_by_area.csv, quality_by_region.csv and data_quality.json.

Run after pcso.py:  python src/tables.py
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd

from common import DERIVED, RAW, REGION_TO_AREA, WORK, Z, lonlat_to_tile, metro_of, quadkey, read_rwi

UTM = "EPSG:32651"
# PCSO Annual Report CY2023, lotto agents by area at 31 December 2023. The PDF blocks scripts;
# these figures were read through a search index on 30 October 2026 and are unverified.
CY2023_AGENTS = {"National Capital Region": 1850, "Northern and Central Luzon": 1111,
                 "Southern Luzon and Bicol Region": 1695, "Visayas": 1124, "Mindanao": 636}
CY2023_PRINTED_TOTAL = 6494


def key_of(tx, ty):
    return np.asarray(tx).astype(np.int64) * 100000 + np.asarray(ty)


def sig(x):
    return float(f"{x:.6g}")


b = pd.read_parquet(WORK / "barangays.parquet")
b["pcso_area"] = b.adm1_pcode.map(REGION_TO_AREA)
b["metro"] = metro_of(b.adm1_pcode, b.adm2_name, b.adm3_name)
o = pd.read_parquet(WORK / "pcso_outlets.parquet")
o["parsed"] = o.coord_kind.isin(["decimal", "dms", "decimal_repaired"])
gps = o.status.str.startswith("gps_")
OUTLET_COLS = {  # column -> which outlets it counts
    "outlets": o.placed,                                   # GPS in a barangay, or address barangay
    "outlets_gps": gps,
    "outlets_gps_consistent": o.status == "gps_consistent",
    "outlets_gps_other_town": o.status == "gps_other_town",
    "outlets_gps_far": o.status == "gps_far",
    "outlets_gps_town_unnamed": o.status == "gps_town_unnamed",
    "outlets_address_barangay": o.status == "address_barangay",
}

# ---------------------------------------------------------------------------
# 1. RWI tiles
# ---------------------------------------------------------------------------
rwi = read_rwi()
tx, ty = lonlat_to_tile(rwi.longitude.values, rwi.latitude.values)
t = pd.DataFrame({"tx": tx, "ty": ty, "lon": rwi.longitude.round(5), "lat": rwi.latitude.round(5),
                  "rwi": rwi.rwi, "rwi_error": rwi.error})
t["key"] = key_of(t.tx, t.ty)
assert not t.key.duplicated().any(), "one RWI row per tile"
t.insert(0, "quadkey", [quadkey(x, y) for x, y in zip(t.tx, t.ty)])
n = 2 ** Z
lat_n = np.arctan(np.sinh(np.pi * (1 - 2 * t.ty / n)))
lat_s = np.arctan(np.sinh(np.pi * (1 - 2 * (t.ty + 1) / n)))
t["tile_km2"] = (6371.0088 ** 2 * (2 * np.pi / n) * (np.sin(lat_n) - np.sin(lat_s))).round(3)
t = t.set_index("key")

# People: census counts spread over pixels, plus barangays with no populated pixel at their
# interior point
pix = pd.read_parquet(WORK / "pixels.parquet", columns=["pop", "pop_census", "b", "tx", "ty"])
pix["key"] = key_of(pix.tx, pix.ty)
pix["urban_pop"] = pix.pop_census * b.urban.values[pix.b]  # NaN where the flag is unknown
pix["flag_pop"] = np.where(np.isnan(b.urban.values[pix.b]), 0.0, pix.pop_census)
nopix = b[b.worldpop == 0]
extra = pd.DataFrame({"pop": 0.0, "pop_census": nopix["pop"].fillna(0).values, "b": nopix.index.values,
                      "key": key_of(nopix.rp_tx, nopix.rp_ty)})
extra["urban_pop"] = extra.pop_census * b.urban.values[extra.b]
extra["flag_pop"] = np.where(np.isnan(b.urban.values[extra.b]), 0.0, extra.pop_census)
people = pd.concat([pix.drop(columns=["tx", "ty"]), extra], ignore_index=True)
del pix
per_tile = people.groupby("key").agg(pop=("pop_census", "sum"), worldpop_2024=("pop", "sum"),
                                     urban_pop=("urban_pop", "sum"), flag_pop=("flag_pop", "sum"),
                                     n_barangays=("b", "nunique"))
t = t.join(per_tile)
t["urban_share"] = (t.urban_pop / t.flag_pop).where(t.flag_pop > 0)
t[["pop", "worldpop_2024"]] = t[["pop", "worldpop_2024"]].fillna(0)
t["n_barangays"] = t.n_barangays.fillna(0).astype(int)

# Province, region, PCSO area, city area: from the barangay holding most of the tile's people;
# tiles with nobody take the barangay under (or nearest to) their RWI point.
bt = people.groupby(["key", "b"]).pop_census.sum().reset_index()
top_b = bt.sort_values("pop_census").drop_duplicates("key", keep="last").set_index("key").b
geoms = gpd.read_parquet(WORK / "barangay_geoms.parquet")
empty = t.index[~t.index.isin(top_b.index)]
centre = gpd.GeoDataFrame(geometry=gpd.points_from_xy(t.loc[empty, "lon"], t.loc[empty, "lat"]),
                          index=empty, crs=4326).to_crs(UTM)
near = gpd.sjoin_nearest(centre, geoms.to_crs(UTM)[["geometry"]], how="left", distance_col="d")
near = near[~near.index.duplicated()]
t["home_b"] = top_b.reindex(t.index).fillna(near.index_right.reindex(t.index)).astype(int)
for c in ["adm2_pcode", "adm2_name", "adm1_pcode", "adm1_name", "pcso_area", "metro"]:
    t[c] = b[c].values[t.home_b]
t = t.rename(columns={"adm2_pcode": "province_pcode", "adm2_name": "province",
                      "adm1_pcode": "region_pcode", "adm1_name": "region"})
# Each region's people living in a tile with an RWI value (by where they live, not tile labels)
people["region"] = b.adm1_pcode.values[people.b]
pop_in_rwi_by_region = people[people.key.isin(t.index)].groupby("region").pop_census.sum()
del people, bt

# Outlets, commerce and roads onto tiles
ox, oy = lonlat_to_tile(o.lon.fillna(0).values, o.lat.fillna(0).values)
o["key"] = np.where(o.lon.notna(), key_of(ox, oy), -1)
for col, sel in OUTLET_COLS.items():
    t[col] = o[sel].groupby("key").size().reindex(t.index).fillna(0).astype(int)
t["outlets_address_town"] = o[o.status == "address_town"].groupby("key").size().reindex(t.index).fillna(0).astype(int)

cp = pd.read_parquet(WORK / "commerce_points.parquet")
cp["key"] = key_of(cp.tx, cp.ty)
for src in ("osm", "overture"):
    for kind, name in (("shop", f"shops_{src}"), ("food", f"food_{src}")):
        sel = (cp.source == src) & (cp.kind == kind)
        t[name] = cp[sel].groupby("key").size().reindex(t.index).fillna(0).astype(int)
t["shops"] = t.shops_osm + t.shops_overture

rs = np.load(WORK / "road_segments.npz")
rx, ry = lonlat_to_tile(rs["lon"], rs["lat"])
t["road_km"] = pd.Series(rs["km"]).groupby(key_of(rx, ry)).sum().reindex(t.index).fillna(0).round(3)

# ---------------------------------------------------------------------------
# 2. Barangays
# ---------------------------------------------------------------------------
for col, sel in OUTLET_COLS.items():
    b[col] = np.bincount(o.b[sel & o.placed], minlength=len(b))
b["shops"] = b.shops_osm + b.shops_overture
b["main_tile"] = [quadkey(int(k // 100000), int(k % 100000)) for k in b.main_tile_key]

# ---------------------------------------------------------------------------
# 3. Write the tables
# ---------------------------------------------------------------------------
tile_cols = ["quadkey", "lon", "lat", "tile_km2", "rwi", "rwi_error", *OUTLET_COLS, "outlets_address_town",
             "pop", "worldpop_2024", "n_barangays", "urban_share", "shops", "shops_osm", "shops_overture",
             "food_osm", "food_overture", "road_km", "province_pcode", "province", "region_pcode", "region",
             "pcso_area", "metro"]
tiles = t[tile_cols].copy()
tiles[["pop", "worldpop_2024"]] = tiles[["pop", "worldpop_2024"]].round(1)
tiles["urban_share"] = tiles.urban_share.round(4)
tiles.sort_values("quadkey").to_csv(DERIVED / "tiles.csv", index=False)

brgy = b.rename(columns={"adm2_pcode": "province_pcode", "adm2_name": "province",
                         "adm1_pcode": "region_pcode", "adm1_name": "region"})
brgy_cols = ["adm4_pcode", "adm4_name", "adm3_pcode", "adm3_name", "province_pcode", "province",
             "region_pcode", "region", "pcso_area", "metro", "area_sqkm", "pop", "pop_source",
             "worldpop", "urban", "rwi", "rwi_error", "rwi_source", "main_tile", "n_tiles", *OUTLET_COLS,
             "shops", "shops_osm", "shops_overture", "food_osm", "food_overture", "road_km"]
brgy = brgy[brgy_cols].rename(columns={"worldpop": "worldpop_2024", "area_sqkm": "area_km2"})
brgy[["pop", "worldpop_2024"]] = brgy[["pop", "worldpop_2024"]].round(1)
brgy[["rwi", "rwi_error"]] = brgy[["rwi", "rwi_error"]].round(4)
brgy[["area_km2", "road_km"]] = brgy[["area_km2", "road_km"]].round(3)
brgy.to_csv(DERIVED / "barangays.csv", index=False)
print(f"tiles.csv: {len(tiles):,} rows   barangays.csv: {len(brgy):,} rows")

# ---------------------------------------------------------------------------
# 4. Data quality
# ---------------------------------------------------------------------------
STATUSES = ["gps_consistent", "gps_other_town", "gps_far", "gps_town_unnamed", "address_barangay",
            "address_town", "unplaced_town_ambiguous", "unplaced"]
by_area = pd.crosstab(o.area, o.status).reindex(columns=STATUSES, fill_value=0)
by_area.insert(0, "outlets", by_area.sum(axis=1))
by_area["parsed_coordinates"] = o.groupby("area").parsed.sum()
by_area["repaired_coordinates"] = o[o.coord_kind == "decimal_repaired"].groupby("area").size()
by_area["placed_in_barangay"] = o.groupby("area").placed.sum()
by_area["in_rwi_tile"] = o[o.placed & o.key.isin(t.index)].groupby("area").size()
by_area["cy2023_agents"] = pd.Series(CY2023_AGENTS)
by_area["map_vs_cy2023"] = (by_area.outlets / by_area.cy2023_agents).round(3)
by_area["placed_vs_cy2023"] = (by_area.placed_in_barangay / by_area.cy2023_agents).round(3)
pop_area = b.groupby("pcso_area")["pop"].sum()
by_area["pop_2020"] = pop_area.round(0)
by_area["outlets_per_100k"] = (by_area.outlets / pop_area * 1e5).round(2)
by_area["cy2023_agents_per_100k"] = (by_area.cy2023_agents / pop_area * 1e5).round(2)
order = list(CY2023_AGENTS)
by_area = by_area.reindex(order)
total = by_area.sum(numeric_only=True)
for c in ["map_vs_cy2023", "placed_vs_cy2023"]:
    total[c] = round(total.outlets / total.cy2023_agents, 3) if c == "map_vs_cy2023" else \
        round(total.placed_in_barangay / total.cy2023_agents, 3)
total["outlets_per_100k"] = round(total.outlets / b["pop"].sum() * 1e5, 2)
total["cy2023_agents_per_100k"] = round(total.cy2023_agents / b["pop"].sum() * 1e5, 2)
by_area.loc["Total"] = total
by_area.index.name = "pcso_area"
by_area.astype({c: "int64" for c in by_area.columns if c not in
                ("map_vs_cy2023", "placed_vs_cy2023", "outlets_per_100k", "cy2023_agents_per_100k")}) \
    .to_csv(DERIVED / "quality_by_area.csv")

# By region: outlets by the region they were placed in (town-only ones by their town's region)
region_names = b.drop_duplicates("adm1_pcode").set_index("adm1_pcode").adm1_name
by_region = pd.crosstab(o.adm1_pcode, o.status).reindex(columns=STATUSES[:-2], fill_value=0)
by_region.insert(0, "outlets_located", by_region.sum(axis=1))
by_region["gps_flagged_share"] = ((by_region.gps_other_town + by_region.gps_far + by_region.gps_town_unnamed)
                                  / by_region[[c for c in by_region.columns if c.startswith("gps_")]].sum(axis=1)).round(3)
by_region["address_placed_share"] = ((by_region.address_barangay + by_region.address_town)
                                     / by_region.outlets_located).round(3)
g = b.groupby("adm1_pcode")
by_region["barangays"] = g.size()
by_region["barangays_no_census_match"] = g.census_pop.apply(lambda s: s.isna().sum())
by_region["barangays_rwi_missing"] = g.rwi_source.apply(lambda s: (s == "none").sum())
by_region["barangays_rwi_from_centre_tile"] = g.rwi_source.apply(lambda s: (s == "centre_tile").sum())
in_rwi = t[t.rwi.notna()]
by_region["pop_2020"] = g["pop"].sum().round(0)
by_region["pop_share_in_rwi_tiles"] = (pop_in_rwi_by_region / by_region.pop_2020).round(4)
by_region["shops_osm"] = g.shops_osm.sum()
by_region["shops_overture"] = g.shops_overture.sum()
by_region["shops_per_1k_people"] = ((by_region.shops_osm + by_region.shops_overture) / by_region.pop_2020 * 1e3).round(2)
by_region.insert(0, "region", region_names.reindex(by_region.index))
by_region.insert(1, "pcso_area", by_region.index.map(REGION_TO_AREA))
by_region.index.name = "region_pcode"
by_region.sort_index().to_csv(DERIVED / "quality_by_region.csv")

pop_all = b["pop"].sum()
quality = {
    "pcso_pull_date": (RAW / "pcso_pull_date.txt").read_text().strip(),
    "osm_extract_date": (RAW / "osm_extract_date.txt").read_text().strip(),
    "outlets": int(len(o)),
    "coordinates_parse": {k: int(v) for k, v in o.coord_kind.value_counts().items()},
    "coordinates_parsed": int(o.parsed.sum()),
    "coordinates_parsed_share": sig(o.parsed.mean()),
    "status": {s: int((o.status == s).sum()) for s in STATUSES},
    "placed_in_barangay": int(o.placed.sum()),
    "placed_in_barangay_share": sig(o.placed.mean()),
    "placed_in_barangay_or_town": int((o.placed | (o.status == "address_town")).sum()),
    "geocoded_from_address": {"needed": int((~gps).sum()),  # no usable coordinates, or off land
                              "to_barangay": int((o.status == "address_barangay").sum()),
                              "to_town_only": int((o.status == "address_town").sum()),
                              "unplaced": int(o.status.str.startswith("unplaced").sum())},
    "gps_far_median_km": sig(o.loc[o.status == "gps_far", "named_town_km"].median()),
    "placed_outlets_outside_rwi_tiles": int((o.placed & ~o.key.isin(in_rwi.index)).sum()),
    "tiles": int(len(t)), "tiles_with_people": int((t["pop"] > 0).sum()),
    "tiles_with_outlets": int((t.outlets > 0).sum()),
    "barangays": int(len(b)), "barangays_with_outlets": int((b.outlets > 0).sum()),
    "pop_total": sig(pop_all), "pop_in_rwi_tiles": sig(in_rwi["pop"].sum()),
    "pop_share_in_rwi_tiles": sig(in_rwi["pop"].sum() / pop_all),
    "cy2023_agents_by_area_sum": int(sum(CY2023_AGENTS.values())),
    "cy2023_agents_printed_total": CY2023_PRINTED_TOTAL,
    "map_vs_cy2023_printed_total": sig(len(o) / CY2023_PRINTED_TOTAL),
}
with open(DERIVED / "data_quality.json", "w") as fh:
    json.dump(quality, fh, indent=2)
    fh.write("\n")
print(json.dumps(quality, indent=2))
print(by_area.to_string())
