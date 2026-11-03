#!/usr/bin/env python3
"""
Vector tiles for the interactive web map in docs/map/ (MapLibre GL JS reading PMTiles).

  docs/map/data/tiles.pmtiles          every RWI tile: people, outlets, outlets per 100,000,
                                       RWI, wealth quintile, wealth x outlet-rate class, and the
                                       main national count model's residual and LISA cluster
  docs/map/data/ncr_barangays.pmtiles  NCR barangays (simplified outlines): the same, with
                                       NCR's own quintiles and the NCR barangay model's residuals
  docs/map/data/cebu_barangays.pmtiles, davao_barangays.pmtiles
                                       the same for Metro Cebu and Metro Davao
  docs/map/data/summary.json           the headline rate ratios the map's panel shows
  docs/map/data/outlets_local.pmtiles  outlet points, built for local viewing only and
                                       gitignored: PCSO's outlet list is never committed (see
                                       docs/data-quality.md), only counts per tile and barangay

The wealth x outlet-rate class crosses wealth terciles (population-weighted, within the
layer's scope) with three outlet levels: no outlet, an outlet rate at or below the scope's
overall rate, and above it. The residual is the mid-quantile residual of the count model
with urban share (no shops): positive where a unit has more outlets than wealth, urban share
and its province (or, in the three cities, its city or municipality) alone account for.

Needs tippecanoe 2.17 or later on the path (brew install tippecanoe).

Run after 03_analyse.sh (the notebooks):  ./04_build_map.sh  or  python src/04_build_map/build_map_tiles.py
"""
import json
import shutil
import subprocess

import geopandas as gpd
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))  # shared helpers in src/shared/

from analysis_samples import CITIES, TABLES
from common import DERIVED, ROOT, WORK
from map_layers import map_classes, tile_polygons

MAP = ROOT / "docs" / "map" / "data"
MAP.mkdir(parents=True, exist_ok=True)
TIPPECANOE = shutil.which("tippecanoe")
if TIPPECANOE is None:
    raise SystemExit("build_map_tiles.py needs tippecanoe on the path: brew install tippecanoe "
                     "(or build it from https://github.com/felt/tippecanoe)")


def tippecanoe(src, dst, layer, *args):
    subprocess.run([TIPPECANOE, "-o", str(dst), "--force", "-l", layer, "--quiet",
                    "--no-tile-size-limit", *args, str(src)], check=True)
    return dst.stat().st_size


def write_geojson(gdf, path):
    gdf.to_file(path, driver="GeoJSONSeq")
    return path


def rounded(df, cols, digits):
    for c in cols:
        df[c] = df[c].astype(float).round(digits)
    return df


sizes = {}

# --- National tiles --------------------------------------------------------------------
t = pd.read_csv(DERIVED / "tiles.csv", dtype={"quadkey": str})
t, national_rate = map_classes(t)
res = pd.read_parquet(WORK / "residuals_national_tiles.parquet")
t = t.merge(res[["quadkey", "quantile_residual", "cluster"]], on="quadkey", how="left")
t = t.rename(columns={"cluster": "lisa"})
t["lisa"] = t.lisa.fillna("No people")
geom = tile_polygons(t.quadkey)
cols = ["quadkey", "province", "region", "pop", "outlets", "rate_per_100k", "rwi", "rwi_error", "quintile",
        "bivariate", "shops", "urban_share", "quantile_residual", "lisa"]
tg = gpd.GeoDataFrame(rounded(t[cols].copy(), ["pop"], 0), geometry=geom, crs=4326)
tg = rounded(tg, ["rate_per_100k", "quantile_residual"], 2)
tg = rounded(tg, ["urban_share"], 3)
tg["quintile"] = tg.quintile.astype("Int64")
sizes["tiles.pmtiles"] = tippecanoe(write_geojson(tg, WORK / "map_tiles.geojsons"), MAP / "tiles.pmtiles",
                                    "tiles", "-Z4", "-z11", "--detect-shared-borders",
                                    "--coalesce-densest-as-needed", "--extend-zooms-if-still-dropping")

# --- City barangays (NCR, Metro Cebu, Metro Davao) ---------------------------------------
geoms = gpd.read_parquet(WORK / "barangay_geoms.parquet").set_index("adm4_pcode")
city_rate = {}
for key, scope in (("ncr", "NCR"), ("cebu", "Metro Cebu"), ("davao", "Metro Davao")):
    b = pd.read_csv(DERIVED / "barangays.csv")
    b = b[b.metro == CITIES[scope]].reset_index(drop=True)
    b, city_rate[key] = map_classes(b)
    res = pd.read_parquet(WORK / f"residuals_{key}_barangays.parquet")
    b = b.merge(res[["adm4_pcode", "quantile_residual", "cluster"]], on="adm4_pcode", how="left")
    b = b.rename(columns={"cluster": "lisa"})
    b["lisa"] = b.lisa.fillna("No people")
    bg = gpd.GeoDataFrame(b, geometry=geoms.geometry.reindex(b.adm4_pcode).to_numpy(), crs=4326)
    bg["geometry"] = bg.to_crs(32651).simplify(5, preserve_topology=True).to_crs(4326)
    cols = ["adm4_pcode", "adm4_name", "adm3_name", "pop", "outlets", "rate_per_100k", "rwi", "rwi_error",
            "quintile", "bivariate", "shops", "urban_share", "main_tile", "quantile_residual", "lisa", "geometry"]
    bg = rounded(bg[cols].copy(), ["pop"], 0)
    bg = rounded(bg, ["rate_per_100k", "quantile_residual", "rwi", "rwi_error"], 2)
    bg = rounded(bg, ["urban_share"], 3)
    bg["quintile"] = bg.quintile.astype("Int64")
    name = f"{key}_barangays.pmtiles"
    sizes[name] = tippecanoe(write_geojson(bg, WORK / f"map_{key}_barangays.geojsons"), MAP / name, "barangays",
                             "-Z8", "-z14", "--detect-shared-borders", "--no-tiny-polygon-reduction",
                             "--no-feature-limit")

# --- Outlet points, local only ---------------------------------------------------------
o = pd.read_parquet(WORK / "pcso_outlets.parquet")
o = o[o.lon.notna() & (o.placed | (o.status == "address_town"))]
og = gpd.GeoDataFrame(o[["status"]], geometry=gpd.points_from_xy(o.lon, o.lat), crs=4326)
tippecanoe(write_geojson(og, WORK / "map_outlets.geojsons"), MAP / "outlets_local.pmtiles", "outlets",
           "-Z5", "-z14", "-r1", "--no-feature-limit")

# --- Panel numbers ---------------------------------------------------------------------
m = pd.read_csv(TABLES / "models.csv")
headline = []
scope_units = [("National", "tile"), ("National", "barangay")]
scope_units += [(scope, unit) for scope in CITIES for unit in ("barangay", "tile")]
for scope, unit in scope_units:
    for model in ("count", "presence"):
        for variant in ("+ urban share", "+ shops"):
            r = m[(m.scope == scope) & (m.unit == unit) & (m.model == model) & (m.variant == variant)]
            if r.empty:  # not estimable, e.g. NCR tiles, where almost every tile has an outlet
                continue
            r = r.iloc[0]
            headline.append({"scope": scope, "unit": unit, "model": model, "variant": variant,
                             "estimate": r.estimate, "ratio": round(r.wealth_ratio, 3),
                             "ci_low": round(r.ci_low, 3), "ci_high": round(r.ci_high, 3), "n": int(r.n)})
summary = {"national_rate_per_100k": round(national_rate, 2),
           **{f"{key}_rate_per_100k": round(rate, 2) for key, rate in city_rate.items()},
           "wealth_unit": m.wealth_unit.iloc[0], "models": headline}
(MAP / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False) + "\n")
for k, v in sizes.items():
    print(f"{k}: {v / 1e6:.1f} MB")
