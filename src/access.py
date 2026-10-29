#!/usr/bin/env python3
"""
Access as people experience it (review step 8): walking distance over the OSM path and
road network from where people live (WorldPop 100 m pixels) to the nearest mapped lotto
outlet, summarised by within-city wealth quintile, after Robitaille and Herjean (2008).

Run for the three city areas only. Nationally the outcome holds about 11% of outlets, so
distances there would mostly measure mapping gaps. Even in the cities these are distances
to the nearest *mapped* outlet, so they are upper bounds on the true distance.

Each city area gets its own graph: walkable OSM ways inside the area's bounding box plus
3 km, kept to the largest connected component. Outlets (the OSM plus Overture union) join
the graph through a virtual source linked to each outlet's nearest node by the straight
snapping distance; people join at their pixel's nearest node, plus the snapping distance.

Writes data/derived/access_quintiles.csv (all three areas, then each area, by quintile)
and data/derived/access.json.

Run after cities.py:  python src/access.py
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import scipy.sparse as sp
import shapely
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

from common import DERIVED, RAW, WORK, area_of, weighted_quantiles
from countmodels import sig

BUFFER_DEG = 0.03  # about 3 km
NO_WALK_FLAG = 100


def xy(lon, lat, lat0):
    """Local equirectangular metres, accurate to well under 1% across one city."""
    return np.column_stack([np.asarray(lon) * 111_320 * np.cos(np.radians(lat0)),
                            np.asarray(lat) * 110_570])


b = pd.read_parquet(WORK / "barangays.parquet")
b["area"] = area_of(b)
s = b[(b.area != "Rest of the country") & (b["pop"] > 0) & b.rwi.notna()].copy()
s["quintile"] = weighted_quantiles(s.rwi.values, s["pop"].values, 5) + 1  # as in cities.py
geoms = gpd.read_parquet(WORK / "barangay_geoms.parquet").set_index("adm4_pcode").loc[s.adm4_pcode]
s_geom = geoms.geometry.values

w = np.load(WORK / "osm_ways.npz")
lon_all, lat_all, ref_all, off, cls = w["lon"], w["lat"], w["ref"], w["offsets"], w["cls"]
walk_node = np.repeat(cls < NO_WALK_FLAG, np.diff(off))
seg_ok = np.ones(len(lon_all), dtype=bool)
seg_ok[off[1:] - 1] = False  # a way's last node does not start a segment
seg_ok &= walk_node

outlets = pd.read_csv(DERIVED / "outlets_union.csv")
outlets = outlets[outlets["product"] == "lotto"]

with rasterio.open(RAW / "phl_pop_100m.tif") as r:
    pop = r.read(1)
    T = r.transform
rows, cols = np.where(pop > 0)
pix_lon, pix_lat, pix_pop = T.c + (cols + 0.5) * T.a, T.f + (rows + 0.5) * T.e, pop[rows, cols].astype(float)
del pop

tree = shapely.STRtree(s_geom)
results = []
for area in ["Metro Manila (NCR)", "Metro Cebu", "Davao City"]:
    ga = shapely.union_all(s_geom[(s.area == area).values])
    x0, y0, x1, y1 = ga.bounds
    lat0 = (y0 + y1) / 2
    box = (x0 - BUFFER_DEG, y0 - BUFFER_DEG, x1 + BUFFER_DEG, y1 + BUFFER_DEG)

    # graph: walkable segments with both ends inside the buffered box
    inb = (lon_all >= box[0]) & (lon_all <= box[2]) & (lat_all >= box[1]) & (lat_all <= box[3])
    a = np.where(seg_ok & inb & np.roll(inb, -1))[0]
    nodes, inv = np.unique(np.concatenate([ref_all[a], ref_all[a + 1]]), return_inverse=True)
    u, v = inv[:len(a)], inv[len(a):]
    first = np.unique(np.concatenate([ref_all[a], ref_all[a + 1]]), return_index=True)[1]
    both_i = np.concatenate([a, a + 1])[first]
    nxy = xy(lon_all[both_i], lat_all[both_i], lat0)
    length = np.linalg.norm(nxy[u] - nxy[v], axis=1)
    n = len(nodes)
    G = sp.coo_matrix((length, (u, v)), shape=(n, n)).tocsr()
    G = G.maximum(G.T)
    _, comp = connected_components(G, directed=False)
    main = comp == np.bincount(comp).argmax()
    kd = cKDTree(nxy[main])
    main_idx = np.where(main)[0]

    # virtual source: index n, linked to each outlet's nearest node
    o = outlets[(outlets.lon >= box[0]) & (outlets.lon <= box[2]) & (outlets.lat >= box[1]) & (outlets.lat <= box[3])]
    od, oi = kd.query(xy(o.lon, o.lat, lat0))
    G2 = sp.bmat([[G, sp.coo_matrix((n, 1))],
                  [sp.coo_matrix((od + 0.01, (np.zeros(len(oi), int), main_idx[oi])), shape=(1, n)), None]]).tocsr()
    dist = dijkstra(G2, directed=True, indices=n)[:n]

    # people: 100 m pixels inside this area's barangays
    inp = (pix_lon >= x0) & (pix_lon <= x1) & (pix_lat >= y0) & (pix_lat <= y1)
    px, py, pp = pix_lon[inp], pix_lat[inp], pix_pop[inp]
    qi, qb = tree.query(shapely.points(px, py), predicate="intersects")
    keep = ~pd.Series(qi).duplicated().values
    qi, qb = qi[keep], qb[keep]
    in_area = (s.area.values[qb] == area)
    qi, qb = qi[in_area], qb[in_area]
    pd_, pn = kd.query(xy(px[qi], py[qi], lat0))
    results.append(pd.DataFrame({"area": area, "adm4_pcode": s.adm4_pcode.values[qb],
                                 "quintile": s.quintile.values[qb], "pop": pp[qi],
                                 "dist_m": pd_ + dist[main_idx[pn]]}))
    print(f"{area}: graph {n:,} nodes ({main.mean():.1%} in the main component), "
          f"{len(o)} outlets, {len(qi):,} populated pixels, {pp[qi].sum():,.0f} people")

px = pd.concat(results, ignore_index=True)


def summarise(g):
    w_ = g["pop"].values
    d = g.dist_m.values
    order = np.argsort(d)
    cw = np.cumsum(w_[order]) / w_.sum()
    return pd.Series({"population_worldpop": w_.sum(),
                      "mean_m": np.average(d, weights=w_),
                      "median_m": d[order][np.searchsorted(cw, 0.5)],
                      "share_within_500m": w_[d <= 500].sum() / w_.sum(),
                      "share_within_1km": w_[d <= 1000].sum() / w_.sum()})


by_q = px.groupby("quintile")[["pop", "dist_m"]].apply(summarise).reset_index()
by_q.insert(0, "area", "All three")
by_aq = px.groupby(["area", "quintile"])[["pop", "dist_m"]].apply(summarise).reset_index()
by_q = pd.concat([by_q, by_aq], ignore_index=True)
by_area = px.groupby("area")[["pop", "dist_m"]].apply(summarise).reset_index()
by_q.round({"population_worldpop": 0, "mean_m": 0, "median_m": 0, "share_within_500m": 3,
            "share_within_1km": 3}).to_csv(DERIVED / "access_quintiles.csv", index=False)
print(by_q.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
print(by_area.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
with open(DERIVED / "access.json", "w") as fh:
    json.dump({"by_area": {r.area: {k: sig(r[k]) for k in by_area.columns if k != "area"}
                           for _, r in by_area.iterrows()},
               "pixels": int(len(px))}, fh, indent=2)
    fh.write("\n")
print("Written data/derived/access_quintiles.csv and data/derived/access.json")
