#!/usr/bin/env python3
"""
Build the barangay table the redesigned study runs on.

One row per barangay (OCHA COD-AB, PSGC-coded), carrying:
  - 2020 census population and the PSA urban/rural flag (OCHA's 2020 census table),
    joined on PSGC and, where codes changed since 2020, on municipality and barangay name;
  - wealth: the population-weighted mean Relative Wealth Index of the 2.4 km tiles the
    barangay's people live in, using WorldPop 100 m pixels as the weights;
  - outcomes: lotto outlets (OSM, Overture, union) and Small Town Lottery points;
  - commerce: mapped retail and food points from OSM and from Overture, and OSM road length.

Writes data/work/barangays.parquet (attributes) and data/work/barangay_geoms.parquet.

Run after osm_extract.py and outlets.py:  python src/barangays.py
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
xwalk = dict.fromkeys(set(geo.adm4_pcode) & set(census.census_pcode))
xwalk = {k: k for k in xwalk}
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
# 2. WorldPop 100 m pixels -> barangay; carries population weights and tile RWI
# ---------------------------------------------------------------------------
with rasterio.open(RAW / "phl_pop_100m.tif") as r:
    pop = r.read(1)
    T = r.transform
rows, cols_ = np.where(pop > 0)
pix = pd.DataFrame({"lon": T.c + (cols_ + 0.5) * T.a, "lat": T.f + (rows + 0.5) * T.e,
                    "pop": pop[rows, cols_].astype(float)})
del pop
tree = shapely.STRtree(geo.geometry.values)
pts = shapely.points(pix.lon.values, pix.lat.values)
pi, bi = tree.query(pts, predicate="intersects")
first = ~pd.Series(pi).duplicated().values  # a pixel on a shared edge goes to one barangay
pix["b"] = -1
pix.loc[pi[first], "b"] = bi[first]
print(f"WorldPop 100 m pixels: {len(pix):,}, in a barangay: {(pix.b >= 0).mean():.2%}")

rwi = read_rwi()
rtx, rty = lonlat_to_tile(rwi.longitude.values, rwi.latitude.values)
rwi_by_tile = pd.Series(rwi.rwi.values, index=rtx.astype(np.int64) * 100000 + rty).groupby(level=0).mean()
ptx, pty = lonlat_to_tile(pix.lon.values, pix.lat.values)
pix["rwi"] = rwi_by_tile.reindex(ptx.astype(np.int64) * 100000 + pty).values
pix = pix[pix.b >= 0]
pix["w"] = np.where(pix.rwi.notna(), pix["pop"], 0.0)
pix["rwi_w"] = pix.rwi.fillna(0) * pix.w
agg = pix.groupby("b").agg(worldpop=("pop", "sum"), w=("w", "sum"), rwi_w=("rwi_w", "sum"))
geo["worldpop"] = agg.worldpop.reindex(geo.index).fillna(0).values
geo["rwi"] = (agg.rwi_w / agg.w).reindex(geo.index).values
# A barangay with no populated pixel carrying RWI takes the tile under its interior point
rp = geo.geometry.representative_point()
ftx, fty = lonlat_to_tile(rp.x.values, rp.y.values)
fallback = rwi_by_tile.reindex(ftx.astype(np.int64) * 100000 + fty).values
geo["rwi_source"] = np.where(geo.rwi.notna(), "pixels", np.where(~np.isnan(fallback), "centre_tile", "none"))
geo["rwi"] = geo.rwi.fillna(pd.Series(fallback, index=geo.index))
del pix, pts

geo["pop_source"] = np.where(geo.census_pop.notna(), "census", "worldpop")
geo["pop"] = geo.census_pop.fillna(geo.worldpop)
geo["urban"] = (geo.urban_rural == "U").astype(float).where(geo.urban_rural.notna())

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


outlets = pd.read_csv(DERIVED / "outlets_union.csv")
outlets["b"] = assign(outlets.lon, outlets.lat)
is_osm, is_lotto = outlets.source == "osm", outlets["product"] == "lotto"
count_into("lotto_osm", outlets.b[is_osm & is_lotto].values)
count_into("lotto_union", outlets.b[is_lotto].values)
count_into("stl_osm", outlets.b[outlets["product"] == "stl"].values)
n_unassigned = int((outlets.b < 0).sum())

osm_retail = pd.read_parquet(WORK / "osm_retail.parquet", columns=["lon", "lat"])
count_into("retail_osm", assign(osm_retail.lon, osm_retail.lat))

ov = pd.read_parquet(RAW / "overture_places_ph.parquet",
                     columns=["lon", "lat", "basic_category", "hierarchy", "country"])
ov = ov[ov.country == "PH"]
top = ov.hierarchy.map(lambda h: h[0] if h is not None and len(h) else None)
ov_retail = ov[top.isin(["food_and_drink", "shopping"])]
count_into("retail_overture", assign(ov_retail.lon, ov_retail.lat))
# Lotto shops are retail too, so the mapped-share denominator can never be below the numerator
geo["retail_osm"] = np.maximum(geo.retail_osm, geo.lotto_osm + geo.stl_osm)
geo["retail_all"] = geo.retail_osm + geo.retail_overture

# ---------------------------------------------------------------------------
# 4. Road length per barangay: each OSM road segment counted where its midpoint falls
# ---------------------------------------------------------------------------
w = np.load(WORK / "osm_ways.npz")
lon, lat, off, cls = w["lon"], w["lat"], w["offsets"], w["cls"] % 100
seg_way = np.repeat(np.arange(len(cls)), np.diff(off))
start = np.ones(len(lon), dtype=bool)
start[off[1:] - 1] = False  # a way's last node does not start a segment
a = np.where(start)[0]
seg_cls = cls[seg_way[a]]
road = seg_cls < len(ROAD_CLASSES)
a = a[road]
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
del w, lon, lat

# ---------------------------------------------------------------------------
# 5. Save
# ---------------------------------------------------------------------------
attrs = geo.drop(columns="geometry")
attrs.to_parquet(WORK / "barangays.parquet", index=False)
geo[["adm4_pcode", "geometry"]].to_parquet(WORK / "barangay_geoms.parquet", index=False)

summary = {
    "n_barangays": int(len(geo)),
    "census_join_on_psgc": n_code, "census_join_on_name": n_name,
    "census_unmatched_barangays": int(geo.census_pcode.isna().sum()),
    "census_pop_matched": sig(geo.census_pop.sum()), "census_pop_total": sig(census.census_pop.sum()),
    "pop_total_used": sig(geo["pop"].sum()),
    "rwi_from_pixels": int((geo.rwi_source == "pixels").sum()),
    "rwi_from_centre_tile": int((geo.rwi_source == "centre_tile").sum()),
    "rwi_missing": int((geo.rwi_source == "none").sum()),
    "outlets_unassigned": n_unassigned,
    "lotto_osm": int(geo.lotto_osm.sum()), "lotto_union": int(geo.lotto_union.sum()),
    "stl_osm": int(geo.stl_osm.sum()),
    "retail_osm": int(geo.retail_osm.sum()), "retail_overture": int(geo.retail_overture.sum()),
    "road_km": sig(geo.road_km.sum()),
    "osm_extract_date": (RAW / "osm_extract_date.txt").read_text().strip(),
}
with open(DERIVED / "barangays_summary.json", "w") as fh:
    json.dump(summary, fh, indent=2)
    fh.write("\n")
print(json.dumps(summary, indent=2))
