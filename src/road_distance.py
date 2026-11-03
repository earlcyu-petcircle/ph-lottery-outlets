#!/usr/bin/env python3
"""
Road distance from where people live to the nearest PCSO lotto outlet, by wealth group (RQ4).

People are the 2024 census counts on WorldPop 100 m pixels (data/work/pixels.parquet). The
network is every OpenStreetMap road of the classes counted in road_km, in either direction.
Each pixel and each outlet is joined to its nearest road node by a straight leg, and one
shortest-path search from all outlets at once gives every node its distance to the nearest
outlet. A pixel's distance is its leg plus its node's network distance. People on a road
network with no outlet (mostly small islands) have no road distance and are counted apart.
Straight-line distance to the nearest outlet is reported alongside for everyone.

Wealth groups are the same population-weighted RWI quintiles as the descriptive pass:
nationally by the pixel's RWI tile, in NCR by the pixel's barangay among NCR barangays.

Writes results/tables/road_distance.csv.

Run after tables.py:  python src/road_distance.py
"""
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from analysis_data import BARANGAYS, NCR, TABLES, TILES, weighted_quintile
from common import DERIVED, ROAD_CLASSES, WORK

KM_PER_DEG_LAT = 110.574
THRESHOLDS_KM = (1, 2, 5)


def xy(lon, lat):
    """Local planar km (equirectangular at each point's latitude): accurate for short legs."""
    return np.column_stack([lon * 111.320 * np.cos(np.radians(lat)), lat * KM_PER_DEG_LAT])


def haversine_km(lon1, lat1, lon2, lat2):
    la1, la2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin(dl / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(h))


def weighted_quantile(v, w, q):
    o = np.argsort(v)
    c = np.cumsum(w[o])
    return v[o][np.searchsorted(c, q * c[-1])]


# --- Road graph ------------------------------------------------------------------------
wz = np.load(WORK / "osm_ways.npz")
off, cls, ref, lon, lat = wz["offsets"], wz["cls"] % 100, wz["ref"], wz["lon"], wz["lat"]
seg_way = np.repeat(np.arange(len(cls)), np.diff(off))
start = np.ones(len(ref), dtype=bool)
start[off[1:] - 1] = False
a = np.flatnonzero(start & (cls[seg_way] < len(ROAD_CLASSES)))
nodes, inv = np.unique(ref, return_inverse=True)
node_lon = np.zeros(len(nodes))
node_lat = np.zeros(len(nodes))
node_lon[inv], node_lat[inv] = lon, lat
u, v = inv[a], inv[a + 1]
km = haversine_km(lon[a], lat[a], lon[a + 1], lat[a + 1])
used = np.unique(np.concatenate([u, v]))  # road nodes only (paths and tracks left out)
del wz, ref, lon, lat, seg_way, start, inv
print(f"road graph: {len(used):,} nodes, {len(a):,} segments, {km.sum():,.0f} km", flush=True)

# --- Outlets onto the graph, one search from all of them ---------------------------------
o = pd.read_parquet(WORK / "pcso_outlets.parquet")
o = o[o.placed & o.lon.notna()]  # the outlets counted in `outlets`
tree = cKDTree(xy(node_lon[used], node_lat[used]))
leg_o, i_o = tree.query(xy(o.lon.to_numpy(), o.lat.to_numpy()))
src = len(nodes)  # a virtual source joined to each outlet's node by the outlet's leg
g = sparse.coo_matrix((np.concatenate([km, km, leg_o]),
                       (np.concatenate([u, v, np.full(len(o), src)]),
                        np.concatenate([v, u, used[i_o]]))),
                      shape=(len(nodes) + 1, len(nodes) + 1)).tocsr()
dist = dijkstra(g, directed=True, indices=src)
del g
print(f"outlets on the graph: {len(o):,} (median leg {np.median(leg_o) * 1000:.0f} m)", flush=True)

# --- People ---------------------------------------------------------------------------
pix = pd.read_parquet(WORK / "pixels.parquet", columns=["lon", "lat", "pop_census", "b", "tx", "ty"])
pix = pix[pix.pop_census > 0].reset_index(drop=True)
leg_p, i_p = tree.query(xy(pix.lon.to_numpy(), pix.lat.to_numpy()))
pix["road_km"] = leg_p + dist[used[i_p]]
pix["line_km"] = cKDTree(xy(o.lon.to_numpy(), o.lat.to_numpy())).query(xy(pix.lon.to_numpy(), pix.lat.to_numpy()))[0]
del tree

# Wealth groups: national by tile, NCR by barangay (as in descriptives.py)
tq = TILES.assign(quintile=weighted_quintile(TILES.rwi.to_numpy(), TILES["pop"].to_numpy()))
pix["tile_quintile"] = pd.Series(tq.quintile.to_numpy(), index=tq.tx * 100000 + tq.ty) \
    .reindex(pix.tx * 100000 + pix.ty).to_numpy()
b_all = pd.read_csv(DERIVED / "barangays.csv", usecols=["adm4_pcode", "region_pcode"])
nb = BARANGAYS[BARANGAYS.region_pcode == NCR]
nq = pd.Series(weighted_quintile(nb.rwi.to_numpy(), nb["pop"].to_numpy()), index=nb.adm4_pcode)
pix["ncr_quintile"] = nq.reindex(b_all.adm4_pcode.to_numpy()[pix.b]).to_numpy()
pix["in_ncr"] = b_all.region_pcode.to_numpy()[pix.b] == NCR

rows = []
for scope, sel, qcol in (("National", np.ones(len(pix), bool), "tile_quintile"),
                         ("NCR", pix.in_ncr.to_numpy(), "ncr_quintile")):
    d = pix[sel & pix[qcol].notna()]
    for q, g_ in [*d.groupby(qcol), ("All", d)]:
        w = g_.pop_census.to_numpy()
        reach = np.isfinite(g_.road_km.to_numpy())
        r, wr = g_.road_km.to_numpy()[reach], w[reach]
        row = {"scope": scope, "quintile": q if q == "All" else int(q), "people": w.sum(),
               "share_people_no_road_route": 1 - wr.sum() / w.sum(),
               "road_km_median": weighted_quantile(r, wr, .5), "road_km_mean": np.average(r, weights=wr),
               "road_km_p75": weighted_quantile(r, wr, .75), "road_km_p90": weighted_quantile(r, wr, .9)}
        for k in THRESHOLDS_KM:  # among everyone, so people with no road route count as beyond
            row[f"share_people_within_{k}km_road"] = wr[r <= k].sum() / w.sum()
        line = g_.line_km.to_numpy()
        row["line_km_median"] = weighted_quantile(line, w, .5)
        row["line_km_mean"] = np.average(line, weights=w)
        rows.append(row)

out = pd.DataFrame(rows)
out.to_csv(TABLES / "road_distance.csv", index=False, float_format="%.6g")
with pd.option_context("display.width", 200):
    print(out[["scope", "quintile", "people", "road_km_median", "road_km_mean", "share_people_within_2km_road",
               "share_people_no_road_route", "line_km_median"]].round(3).to_string(index=False))
