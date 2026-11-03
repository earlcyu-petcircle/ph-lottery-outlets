#!/usr/bin/env python3
"""
Put every layer except the outlets onto barangays and onto WorldPop 100 m pixels.

One row per barangay (OCHA COD-AB v03, PSGC-coded), carrying:
  - 2024 census population (read_census_2024.py), joined by town and barangay name, since the PSA
    workbooks carry no PSGC codes;
  - urban share: the share of its people in GHSL Degree of Urbanisation urban cells;
  - wealth: the population-weighted mean Relative Wealth Index, and its error, of the
    2.4 km tiles the barangay's people live in, plus the tile holding most of them;
  - commerce: OSM and Overture shop and food points (their lotto points left out) and
    OSM road length.

The pixel table is the dasymetric step (Mennis 2003): every populated WorldPop 2024 100 m
pixel carries its barangay, its RWI tile and its share of the barangay's census count, so
build_tables.py can sum people onto tiles.

Writes data/work/barangays.parquet, barangay_geoms.parquet, pixels.parquet,
commerce_points.parquet, road_segments.npz and data/derived/barangays_summary.json.

Run after extract_osm_shops_and_roads.py:  python src/02_build_tables/build_barangays.py
"""
import difflib
import json
import re
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import rasterio
import rasterio.transform
import rasterio.windows
import shapely

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))  # shared helpers in src/shared/

from common import DERIVED, POPCEN_FILES, RAW, ROAD_CLASSES, WORK, lonlat_to_tile, read_rwi

UTM = "EPSG:32651"
GDB = "zip://" + str(RAW / "phl_admin_boundaries.gdb.zip")
SMOD = "zip://" + str(RAW / "ghs_smod_e2025_1km.zip") + "!GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.tif"


def sig(x):
    return float(f"{x:.6g}")


def tile_key(tx, ty):
    return np.asarray(tx).astype(np.int64) * 100000 + np.asarray(ty)


# ---------------------------------------------------------------------------
# 1. Boundaries and 2024 census population
# ---------------------------------------------------------------------------
cols = ["adm4_pcode", "adm4_name", "adm3_pcode", "adm3_name", "adm2_pcode", "adm2_name",
        "adm1_pcode", "adm1_name", "area_sqkm"]
geo = gpd.read_file(GDB, layer="phl_admin4", columns=cols, engine="pyogrio")
geo = geo.sort_values("adm4_pcode").reset_index(drop=True)
print(f"Barangays (COD-AB): {len(geo):,}")

popcen = pd.read_parquet(WORK / "popcen2024.parquet")  # from read_census_2024.py
popcen["row"] = np.arange(len(popcen))


def _ascii(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def _saints(s):
    return re.sub(r"\bsto\b\.?", "santo", re.sub(r"\bsta\b\.?", "santa", s))


ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8",
         "ix": "9", "x": "10"}


def _numerals(s):
    """Roman numerals as digits, so "Ligas II" and "Ligas 2" agree."""
    return re.sub(r"\b(" + "|".join(sorted(ROMAN, key=len, reverse=True)) + r")\b", lambda m: ROMAN[m.group(1)], s)


def norm_mun(s):
    s = _saints(re.sub(r"\(.*?\)|\bcity of\b|\bcity\b", "", _ascii(s)))
    return re.sub(r"[^a-z0-9]", "", s)


def norm_brgy(s):
    s = re.sub(r"\(.*?\)|\bpoblacion\b|\bpob\b\.?|\bbarangay\b|\bbrgy\b|\bbgy\b", "", _ascii(s))
    return re.sub(r"[^a-z0-9]", "", _numerals(_saints(s)))


def strip_note(s):
    """A 2024 barangay name without a trailing footnote mark ("Saray 2", "Ligas 2 1", "East ²")."""
    return re.sub(r"\s*[\u00b9\u00b2\u00b3\u2070-\u2079]+$|\s+\d{1,2}$", "", s.strip())


def loose(s):
    return re.sub(r"[^a-z0-9]", "", _numerals(_saints(re.sub(r"\(.*?\)", "", _ascii(s)))))


# The 2024 workbooks carry names only, so the join is by name: town first, then barangay
# inside it. COD-AB v03 predates the Negros Island Region, so each workbook is matched against
# the COD-AB regions it covers (POPCEN_FILES).
towns = geo.drop_duplicates("adm3_pcode")[["adm3_pcode", "adm3_name", "adm2_name", "adm1_pcode"]]
towns = towns.assign(k=towns.adm3_name.map(norm_mun), kp=towns.adm2_name.map(norm_mun))
town_of = {}
for f, area, town in popcen[["file", "sheet_area", "town"]].drop_duplicates().itertuples(index=False):
    cand = towns[towns.adm1_pcode.isin(POPCEN_FILES[f])]
    hit = cand[cand.k == norm_mun(town)]
    if len(hit) > 1:  # a town name used in two provinces of the region
        hit = hit[hit.kp == norm_mun(area)]
    if len(hit) == 0 and f == "ncr":  # the City of Manila sheet lists its districts as towns
        hit = cand[cand.k == norm_mun(area)]
    if len(hit) == 1:
        town_of[(f, area, town)] = hit.adm3_pcode.iloc[0]
popcen["adm3_pcode"] = [town_of.get(k) for k in zip(popcen.file, popcen.sheet_area, popcen.town)]
# Where the barangays of an unmatched town are looked for (a new or renamed town, or a
# barangay moved between towns): its province, or all of NCR
prov_of_town = dict(zip(towns.adm3_pcode, towns.adm2_name))
prov_by_name = {}
for f, regions in POPCEN_FILES.items():
    for name in towns[towns.adm1_pcode.isin(regions)].adm2_name.unique():
        prov_by_name[(f, norm_mun(name))] = name
popcen["scope"] = [("PH13" if f == "ncr" else prov_by_name.get((f, norm_mun(a)), prov_of_town.get(t)))
                   for f, a, t in zip(popcen.file, popcen.sheet_area, popcen.adm3_pcode)]
geo["scope"] = np.where(geo.adm1_pcode == "PH13", "PH13", geo.adm2_name)

match = {}  # adm4_pcode -> popcen row
split = {}  # adm4_pcode -> the 2024 rows it holds, for barangays split since COD-AB was drawn


def match_unique(g_keys, p_keys, how):
    """Pair COD-AB and 2024 barangays whose key is unique on both sides of one group."""
    gu = g_keys[~g_keys.duplicated(keep=False) & (g_keys != "")]
    pu = p_keys[~p_keys.duplicated(keep=False) & (p_keys != "")]
    lut = dict(zip(gu.values, gu.index))
    for row, k in zip(pu.index, pu.values):
        if k in lut:
            match[lut[k]] = (row, how)


def left(group_col):
    taken = {r for r, _ in match.values()} | {r for rows in split.values() for r in rows}
    return (geo[~geo.adm4_pcode.isin(match)].set_index("adm4_pcode").groupby(group_col),
            popcen[~popcen.row.isin(taken)].set_index("row"))


# Two keys: norm_brgy drops "Poblacion" and the like, so it can leave a name empty; loose
# keeps them ("Poblacion (Titay)" and "Poblacion" are the same barangay in a town)
KEYS = [(norm_brgy, norm_brgy), (loose, loose)]
KEYS_NOTE = [(gf, lambda s, pf=pf: pf(strip_note(s))) for gf, pf in KEYS]
# Pass 1: exact name inside the town; pass 2: the same without a footnote number
for how, keys in (("name", KEYS), ("name_footnote", KEYS_NOTE)):
    for gf, pf in keys:
        g_left, p_left = left("adm3_pcode")
        p_by_town = dict(list(p_left.groupby("adm3_pcode")))
        for a3, g in g_left:
            if a3 in p_by_town:
                match_unique(g.adm4_name.map(gf), p_by_town[a3].barangay.map(pf), how)
# Pass 3: exact name (with or without the footnote) anywhere in the province, or in NCR
for gf, pf in KEYS + KEYS_NOTE:
    g_left, p_left = left("scope")
    p_by_scope = dict(list(p_left.groupby("scope")))
    for sc, g in g_left:
        if sc in p_by_scope:
            match_unique(g.adm4_name.map(gf), p_by_scope[sc].barangay.map(pf), "name_province")
# Pass 4: a barangay split since COD-AB was drawn (Caloocan's Barangay 176 into 176-A to 176-F):
# two or more 2024 barangays named like an unmatched COD-AB one plus a letter all go to it
g_left, p_left = left("adm3_pcode")
p_by_town = dict(list(p_left.groupby("adm3_pcode")))
for a3, g in g_left:
    if a3 not in p_by_town:
        continue
    pk = p_by_town[a3].barangay.map(lambda s: norm_brgy(strip_note(s)))
    for gc, gk in zip(g.index, g.adm4_name.map(norm_brgy)):
        parts = pk[pk.str.fullmatch(re.escape(gk) + "[a-z]")] if gk else pk.iloc[:0]
        if len(parts) >= 2:
            split[gc] = list(parts.index)
            match[gc] = (parts.index[0], "name_split")
# Pass 5: spelling variants inside the town ("Pooc" and "Pook"): mutual best match, ratio >= 0.8,
# and the same numbers in both names (Bacoor merged its barangays in 2023, so "Ligas I" is not
# "Ligas 2", and Caloocan's Barangay 176 was split into 176-A to 176-F)
g_left, p_left = left("adm3_pcode")
p_by_town = dict(list(p_left.groupby("adm3_pcode")))
for a3, g in g_left:
    if a3 not in p_by_town:
        continue
    gk = dict(zip(g.index, g.adm4_name.map(loose)))
    pk = dict(zip(p_by_town[a3].index, p_by_town[a3].barangay.map(lambda s: loose(strip_note(s)))))
    ratio = {(gc, r): difflib.SequenceMatcher(None, gn, pn).ratio() for gc, gn in gk.items() for r, pn in pk.items()}
    best_g = {gc: max(pk, key=lambda r: ratio[gc, r]) for gc in gk}
    best_p = {r: max(gk, key=lambda gc: ratio[gc, r]) for r in pk}
    for gc, r in best_g.items():
        if best_p[r] == gc and ratio[gc, r] >= 0.8 and re.findall(r"\d+", gk[gc]) == re.findall(r"\d+", pk[r]):
            match[gc] = (r, "fuzzy")

geo["popcen_row"] = geo.adm4_pcode.map({k: r for k, (r, _) in match.items()})
geo["pop_join"] = geo.adm4_pcode.map({k: h for k, (_, h) in match.items()})
geo["census_pop"] = geo.popcen_row.map(popcen["pop"])
for gc, rows in split.items():
    geo.loc[geo.adm4_pcode == gc, "census_pop"] = popcen["pop"].iloc[rows].sum()
popcen["matched"] = popcen.row.isin(geo.popcen_row) | popcen.row.isin([r for rows in split.values() for r in rows])
join_counts = geo.pop_join.value_counts().to_dict()
print(f"2024 census join: {join_counts}, unmatched COD-AB barangays {int(geo.pop_join.isna().sum()):,}, "
      f"2024 people matched {popcen.loc[popcen.matched, 'pop'].sum() / popcen['pop'].sum():.2%}")

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


def smod_at(lon, lat):
    """GHSL Degree of Urbanisation class (2025 epoch, 1 km) under each lon/lat point."""
    with rasterio.open(SMOD) as r:
        x, y = pyproj.Transformer.from_crs("EPSG:4326", r.crs, always_xy=True).transform(lon, lat)
        row, col = rasterio.transform.rowcol(r.transform, x, y)
        row, col = np.asarray(row), np.asarray(col)
        win = rasterio.windows.Window(col.min(), row.min(), col.max() - col.min() + 1, row.max() - row.min() + 1)
        return r.read(1, window=win)[row - row.min(), col - col.min()]


# Urban: GHSL classes 21-23 (urban clusters) and 30 (urban centres); 10-13 are rural or water
pix["urban"] = (smod_at(pix.lon.values, pix.lat.values) >= 21).astype(np.int8)

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

# Population: the 2024 census count, or WorldPop where the barangay has no census match
# Population: the 2024 census count where the barangay matched. An unmatched barangay shares
# out the 2024 people its town (or, for a new town, its province) has left unmatched, in
# proportion to WorldPop, so area totals stay the census totals; with none left, it keeps
# its WorldPop count.
geo["pop_source"] = np.where(geo.census_pop.notna(), "census_2024", "worldpop_2024")
geo["pop"] = geo.census_pop.copy()
unmatched = popcen[~popcen.matched]
for level, col_g, col_p in (("census_2024_town_residual", "adm3_pcode", "adm3_pcode"),
                            ("census_2024_province_residual", "scope", "scope")):
    residual = unmatched[unmatched[col_p].notna()].groupby(col_p)["pop"].sum()
    if level.endswith("province_residual"):  # only rows whose town found no COD-AB match
        residual = unmatched[unmatched.adm3_pcode.isna()].groupby(col_p)["pop"].sum()
    open_ = geo["pop"].isna() & geo[col_g].isin(residual.index)
    wp = geo.loc[open_].groupby(col_g).worldpop.transform("sum")
    share = np.where(wp > 0, geo.loc[open_, "worldpop"] / wp,
                     1 / geo.loc[open_].groupby(col_g).worldpop.transform("size"))
    geo.loc[open_, "pop"] = residual.reindex(geo.loc[open_, col_g]).values * share
    geo.loc[open_, "pop_source"] = level
residual_used = {s: float(geo.loc[geo.pop_source == s, "pop"].sum())
                 for s in ("census_2024_town_residual", "census_2024_province_residual")}
geo["pop"] = geo["pop"].fillna(geo.worldpop)
# Urban share: share of the barangay's WorldPop people in GHSL urban cells; a barangay with
# no populated pixel takes the class under its interior point
up = pix.assign(up=pix["pop"] * pix.urban).groupby("b")[["up", "pop"]].sum()
geo["urban_share"] = (up.up / up["pop"]).reindex(geo.index).values
no_pix = geo.urban_share.isna().values
geo.loc[no_pix, "urban_share"] = (smod_at(geo.rp_lon.values[no_pix], geo.rp_lat.values[no_pix]) >= 21).astype(float)
# Dasymetric step: each pixel carries its share of its barangay's count
pix["pop_census"] = pix["pop"] * (geo["pop"].values[pix.b] / geo.worldpop.values[pix.b])
pix[["lon", "lat", "pop", "pop_census", "urban", "b", "tx", "ty"]].to_parquet(WORK / "pixels.parquet", index=False)
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
    "census_vintage": "2024 Census of Population (PSA), as of 1 July 2024",
    "census_join": {k: int(v) for k, v in join_counts.items()},
    "census_unmatched_barangays": int(geo.census_pop.isna().sum()),
    "census_unmatched_by_region": {k: int(v) for k, v in geo[geo.census_pop.isna()].groupby("adm1_pcode").size().items()},
    "census_2024_rows_unmatched": int((~popcen.matched).sum()),
    "census_2024_pop_unmatched": int(popcen.loc[~popcen.matched, "pop"].sum()),
    "census_2024_unmatched_by_workbook": {f: {"barangays": int(len(d)), "pop": int(d["pop"].sum())}
                                          for f, d in popcen[~popcen.matched].groupby("file")},
    "census_split_barangays": {geo.loc[geo.adm4_pcode == gc, "adm4_name"].iloc[0]: len(rows) for gc, rows in split.items()},
    "census_2024_unmatched_pop_not_placed": sig(popcen.loc[~popcen.matched, "pop"].sum() - sum(residual_used.values())),
    "census_pop_matched": sig(geo.census_pop.sum()), "census_pop_total": sig(popcen["pop"].sum()),
    "pop_source": {k: int(v) for k, v in geo.pop_source.value_counts().items()},
    "pop_by_source": {k: sig(v) for k, v in geo.groupby("pop_source")["pop"].sum().items()},
    "census_2024_unmatched_pop_shared_out": sig(sum(residual_used.values())),
    "urban_share_source": "GHSL GHS-SMOD R2023A, 2025 epoch, classes 21-30",
    "pop_share_urban": sig((geo["pop"] * geo.urban_share).sum() / geo["pop"].sum()),
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
