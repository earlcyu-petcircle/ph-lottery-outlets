#!/usr/bin/env python3
"""
Put every layer except the outlets onto barangays and onto WorldPop 100 m pixels.

One row per barangay (OCHA COD-AB v03, PSGC-coded), carrying:
  - 2020 census population and the PSA urban/rural flag (OCHA's 2020 census table),
    joined on PSGC and, where codes changed since 2020, on municipality and barangay name;
  - wealth: the population-weighted mean Relative Wealth Index, and its error, of the
    2.4 km tiles the barangay's people live in, plus the tile holding most of them;
  - commerce: OSM and Overture shop and food points (their lotto points left out) and
    OSM road length.

The pixel table is the dasymetric step (Mennis 2003): every populated WorldPop 2024 100 m
pixel carries its barangay, its RWI tile and its share of the barangay's census count, so
tables.py can sum people onto tiles.

Writes data/work/barangays.parquet, barangay_geoms.parquet, pixels.parquet,
commerce_points.parquet, road_segments.npz and data/derived/barangays_summary.json.

Run after osm_extract.py:  python src/barangays.py
"""
import json
import re
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely

from common import DERIVED, RAW, ROAD_CLASSES, WORK, lonlat_to_tile, read_rwi

UTM = "EPSG:32651"
GDB = "zip://" + str(RAW / "phl_admin_boundaries.gdb.zip")


def sig(x):
    return float(f"{x:.6g}")


def tile_key(tx, ty):
    return np.asarray(tx).astype(np.int64) * 100000 + np.asarray(ty)


# ---------------------------------------------------------------------------
# 1. Boundaries and census population
# ---------------------------------------------------------------------------
cols = ["adm4_pcode", "adm4_name", "adm3_pcode", "adm3_name", "adm2_pcode", "adm2_name",
        "adm1_pcode", "adm1_name", "area_sqkm"]
geo = gpd.read_file(GDB, layer="phl_admin4", columns=cols, engine="pyogrio")
geo = geo.sort_values("adm4_pcode").reset_index(drop=True)
print(f"Barangays (COD-AB): {len(geo):,}")

census = pd.read_excel(RAW / "phl_census2020_brgy_pop.xlsx", sheet_name="2020 CPH")
census.columns = [re.sub(r"\s+", " ", c).strip() for c in census.columns]
census = census.rename(columns={"New 10 PCODE": "census_pcode", "Mun_City": "mun", "Barangay": "brgy",
                                "Urban / Rural (based on 2020 CPH)": "urban_rural",
                                "2020 Census Popn": "census_pop"})


def _ascii(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def _saints(s):
    return re.sub(r"\bsto\b\.?", "santo", re.sub(r"\bsta\b\.?", "santa", s))


def norm_mun(s):
    s = _saints(re.sub(r"\(.*?\)|\bcity of\b|\bcity\b", "", _ascii(s)))
    return re.sub(r"[^a-z0-9]", "", s)


def norm_brgy(s):
    s = re.sub(r"\(.*?\)|\bpoblacion\b|\bpob\b\.?|\bbarangay\b|\bbrgy\b|\bbgy\b", "", _ascii(s))
    return re.sub(r"[^a-z0-9]", "", _saints(s))


# PSGC codes changed after 2020 in NCR, BARMM and elsewhere: match on code first, then on
# normalised municipality + barangay name for the barangays whose code moved.
xwalk = {k: k for k in set(geo.adm4_pcode) & set(census.census_pcode)}
left_g = geo[~geo.adm4_pcode.isin(xwalk)]
left_c = census[~census.census_pcode.isin(xwalk)]
key_c = (left_c.mun.map(norm_mun) + "|" + left_c.brgy.map(norm_brgy))
unique_c = key_c[~key_c.duplicated(keep=False)]
lookup = dict(zip(unique_c.values, left_c.loc[unique_c.index, "census_pcode"]))
for pc, k in zip(left_g.adm4_pcode, left_g.adm3_name.map(norm_mun) + "|" + left_g.adm4_name.map(norm_brgy)):
    if k in lookup:
        xwalk[pc] = lookup.pop(k)
geo["census_pcode"] = geo.adm4_pcode.map(xwalk)
geo = geo.merge(census[["census_pcode", "urban_rural", "census_pop"]], on="census_pcode", how="left")
n_code = int((geo.census_pcode == geo.adm4_pcode).sum())
n_name = int(geo.census_pcode.notna().sum()) - n_code
print(f"Census join: {n_code:,} on PSGC, {n_name:,} on name, {int(geo.census_pcode.isna().sum()):,} unmatched")

# ---------------------------------------------------------------------------
# 2. WorldPop 100 m pixels -> barangay and RWI tile
# ---------------------------------------------------------------------------
with rasterio.open(RAW / "phl_pop_2024_100m.tif") as r:
    pop = r.read(1)
    T = r.transform
rows, cols_ = np.where(pop > 0)  # also drops the nodata value, which is negative
pix = pd.DataFrame({"lon": T.c + (cols_ + 0.5) * T.a, "lat": T.f + (rows + 0.5) * T.e,
                    "pop": pop[rows, cols_].astype(float)})
del pop, rows, cols_
worldpop_total = pix["pop"].sum()
tree = shapely.STRtree(geo.geometry.values)
pts = shapely.points(pix.lon.values, pix.lat.values)
pi, bi = tree.query(pts, predicate="intersects")
first = ~pd.Series(pi).duplicated().values  # a pixel on a shared edge goes to one barangay
pix["b"] = -1
pix.loc[pi[first], "b"] = bi[first]
del pts, pi, bi
print(f"WorldPop 100 m pixels: {len(pix):,}, in a barangay: {(pix.b >= 0).mean():.2%}")
pix = pix[pix.b >= 0].reset_index(drop=True)
pix["tx"], pix["ty"] = lonlat_to_tile(pix.lon.values, pix.lat.values)

rwi = read_rwi()
rtx, rty = lonlat_to_tile(rwi.longitude.values, rwi.latitude.values)
rwi_tile = pd.DataFrame({"rwi": rwi.rwi.values, "error": rwi.error.values},
                        index=tile_key(rtx, rty)).groupby(level=0).mean()
on = rwi_tile.reindex(tile_key(pix.tx, pix.ty))
pix["rwi"], pix["rwi_error"] = on.rwi.values, on.error.values

# Barangay wealth: population-weighted over the pixels that sit in an RWI tile
w = np.where(pix.rwi.notna(), pix["pop"], 0.0)
agg = pd.DataFrame({"b": pix.b, "pop": pix["pop"], "w": w, "rwi_w": pix.rwi.fillna(0) * w,
                    "err_w": pix.rwi_error.fillna(0) * w}).groupby("b").sum()
geo["worldpop"] = agg["pop"].reindex(geo.index).fillna(0).values
geo["rwi"] = (agg.rwi_w / agg.w).reindex(geo.index).values
geo["rwi_error"] = (agg.err_w / agg.w).reindex(geo.index).values
# A barangay with no populated pixel in an RWI tile takes the tile under its interior point
rp = geo.geometry.representative_point()
geo["rp_lon"], geo["rp_lat"] = rp.x.values, rp.y.values
geo["rp_tx"], geo["rp_ty"] = lonlat_to_tile(rp.x.values, rp.y.values)
fallback = rwi_tile.reindex(tile_key(geo.rp_tx, geo.rp_ty))
geo["rwi_source"] = np.where(geo.rwi.notna(), "pixels", np.where(fallback.rwi.notna().values, "centre_tile", "none"))
geo["rwi"] = geo.rwi.fillna(pd.Series(fallback.rwi.values, index=geo.index))
geo["rwi_error"] = geo.rwi_error.fillna(pd.Series(fallback.error.values, index=geo.index))

# The tile holding most of each barangay's people: the cluster for barangay-level errors
pix["key"] = tile_key(pix.tx, pix.ty)
by_bt = pix.groupby(["b", "key"])["pop"].sum().reset_index()
main = by_bt.sort_values("pop").drop_duplicates("b", keep="last").set_index("b")["key"]
geo["main_tile_key"] = main.reindex(geo.index).fillna(pd.Series(tile_key(geo.rp_tx, geo.rp_ty), index=geo.index)).astype(np.int64).values
geo["n_tiles"] = by_bt.groupby("b").size().reindex(geo.index).fillna(0).astype(int).values

# Population: the census count, or WorldPop where the barangay has no census match
geo["pop_source"] = np.where(geo.census_pop.notna(), "census_2020", "worldpop_2024")
geo["pop"] = geo.census_pop.fillna(geo.worldpop)
geo["urban"] = (geo.urban_rural == "U").astype(float).where(geo.urban_rural.notna())
# Dasymetric step: each pixel carries its share of its barangay's count
pix["pop_census"] = pix["pop"] * (geo["pop"].values[pix.b] / geo.worldpop.values[pix.b])
pix[["lon", "lat", "pop", "pop_census", "b", "tx", "ty"]].to_parquet(WORK / "pixels.parquet", index=False)
del pix, by_bt

# ---------------------------------------------------------------------------
# 3. Points -> barangay (nearest barangay within 1 km for points just offshore)
# ---------------------------------------------------------------------------
geo_utm = geo[["geometry"]].to_crs(UTM)


def assign(lon, lat):
    pts_ = shapely.points(np.asarray(lon), np.asarray(lat))
    qi, qb = tree.query(pts_, predicate="intersects")
    out = np.full(len(pts_), -1)
    keep = ~pd.Series(qi).duplicated().values
    out[qi[keep]] = qb[keep]
    miss = np.where(out < 0)[0]
    if len(miss):
        g = gpd.GeoDataFrame(geometry=gpd.points_from_xy(np.asarray(lon)[miss], np.asarray(lat)[miss]),
                             crs=4326).to_crs(UTM)
        j = gpd.sjoin_nearest(g, geo_utm, how="left", max_distance=1000)
        j = j[~j.index.duplicated()]
        out[miss] = j["index_right"].fillna(-1).astype(int).values
    return out


def count_into(name, b):
    geo[name] = np.bincount(b[b >= 0], minlength=len(geo))


# Shops and food points, with each source's own lotto points left out: commerce is a
# control, so it must not contain the outcome.
LOTTO_NAME = r"lotto|pcso|\bstl\b|lottery"
osm = pd.read_parquet(WORK / "osm_retail.parquet", columns=["lon", "lat", "key", "value", "name"])
osm_lotto = (osm.value == "lottery") | osm.name.str.contains(LOTTO_NAME, case=False, regex=True)
osm = osm[~osm_lotto]
ov = pd.read_parquet(RAW / "overture_places_ph.parquet",
                     columns=["lon", "lat", "name", "category", "hierarchy", "country"])
ov = ov[ov.country == "PH"]
top = ov.hierarchy.map(lambda h: h[0] if h is not None and len(h) else None)
ov_lotto = (ov.category == "lottery_vendor") | ov.name.fillna("").str.contains(LOTTO_NAME, case=False, regex=True)
ov = ov[top.isin(["food_and_drink", "shopping"]) & ~ov_lotto]
pts_c = pd.concat([
    pd.DataFrame({"lon": osm.lon, "lat": osm.lat, "source": "osm",
                  "kind": np.where(osm.key == "shop", "shop", "food")}),
    pd.DataFrame({"lon": ov.lon, "lat": ov.lat, "source": "overture",
                  "kind": np.where(top[ov.index] == "shopping", "shop", "food")}),
], ignore_index=True)
pts_c["b"] = assign(pts_c.lon, pts_c.lat)
pts_c["tx"], pts_c["ty"] = lonlat_to_tile(pts_c.lon.values, pts_c.lat.values)
pts_c.to_parquet(WORK / "commerce_points.parquet", index=False)
for src in ("osm", "overture"):
    for kind in ("shop", "food"):
        sel = (pts_c.source == src) & (pts_c.kind == kind)
        count_into(f"{kind}s_{src}" if kind == "shop" else f"food_{src}", pts_c.b[sel].values)

# ---------------------------------------------------------------------------
# 4. Road length per barangay: each OSM road segment counted where its midpoint falls
# ---------------------------------------------------------------------------
wz = np.load(WORK / "osm_ways.npz")
lon, lat, off, cls = wz["lon"], wz["lat"], wz["offsets"], wz["cls"] % 100
seg_way = np.repeat(np.arange(len(cls)), np.diff(off))
start = np.ones(len(lon), dtype=bool)
start[off[1:] - 1] = False  # a way's last node does not start a segment
a = np.where(start & (cls[seg_way] < len(ROAD_CLASSES)))[0]
la1, la2 = np.radians(lat[a]), np.radians(lat[a + 1])
dl = np.radians(lon[a + 1] - lon[a])
km = 2 * 6371.0088 * np.arcsin(np.sqrt(np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin(dl / 2) ** 2))
mlon, mlat = (lon[a] + lon[a + 1]) / 2, (lat[a] + lat[a + 1]) / 2
road_km = np.zeros(len(geo))
for s in range(0, len(a), 2_000_000):
    b = assign(mlon[s:s + 2_000_000], mlat[s:s + 2_000_000])
    ok = b >= 0
    road_km += np.bincount(b[ok], weights=km[s:s + 2_000_000][ok], minlength=len(geo))
geo["road_km"] = road_km
np.savez(WORK / "road_segments.npz", lon=mlon, lat=mlat, km=km)
del wz, lon, lat

# ---------------------------------------------------------------------------
# 5. Save
# ---------------------------------------------------------------------------
geo.drop(columns="geometry").to_parquet(WORK / "barangays.parquet", index=False)
geo[["adm4_pcode", "geometry"]].to_parquet(WORK / "barangay_geoms.parquet", index=False)

summary = {
    "n_barangays": int(len(geo)),
    "census_vintage": "2020 census (PSA, via OCHA on HDX)",
    "census_join_on_psgc": n_code, "census_join_on_name": n_name,
    "census_unmatched_barangays": int(geo.census_pcode.isna().sum()),
    "census_pop_matched": sig(geo.census_pop.sum()), "census_pop_total": sig(census.census_pop.sum()),
    "pop_total_used": sig(geo["pop"].sum()),
    "worldpop_2024_total": sig(worldpop_total),
    "worldpop_2024_in_a_barangay": sig(geo.worldpop.sum()),
    "barangays_without_populated_pixel": int((geo.worldpop == 0).sum()),
    "rwi_from_pixels": int((geo.rwi_source == "pixels").sum()),
    "rwi_from_centre_tile": int((geo.rwi_source == "centre_tile").sum()),
    "rwi_missing": int((geo.rwi_source == "none").sum()),
    "shops_osm": int(geo.shops_osm.sum()), "food_osm": int(geo.food_osm.sum()),
    "shops_overture": int(geo.shops_overture.sum()), "food_overture": int(geo.food_overture.sum()),
    "lotto_points_left_out": {"osm": int(osm_lotto.sum()), "overture": int(ov_lotto.sum())},
    "commerce_points_unassigned": int((pts_c.b < 0).sum()),
    "road_km": sig(geo.road_km.sum()),
    "osm_extract_date": (RAW / "osm_extract_date.txt").read_text().strip(),
}
with open(DERIVED / "barangays_summary.json", "w") as fh:
    json.dump(summary, fh, indent=2)
    fh.write("\n")
print(json.dumps(summary, indent=2))
