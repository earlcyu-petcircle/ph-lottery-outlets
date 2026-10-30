"""
Shared paths, grid helpers and colours for the pipeline.

Every layer is put on one grid: the Web-Mercator (Bing/OSM) tile grid at zoom 14,
about 2.4 km cells at Philippine latitudes, which is the native grid of the Meta
Relative Wealth Index. Cells are keyed by integer tile indices (tx, ty), so no
spatial-join library is needed for the core join.
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"          # downloads from fetch_data.sh (gitignored)
WORK = ROOT / "data" / "work"        # large intermediates (gitignored)
DERIVED = ROOT / "data" / "derived"  # small tables the paper cites (committed)
FIGURES = ROOT / "figures"
MAPS = ROOT / "maps"
for _d in (WORK, DERIVED, FIGURES, MAPS):
    _d.mkdir(parents=True, exist_ok=True)

Z = 14  # RWI native zoom level

# Muted Archive palette; wealth ramp runs terracotta (poorer) -> cream -> slate-teal (richer)
BG, INK, MUTED, ACCENT, RULE = "#F1EBDD", "#292216", "#665B45", "#96700F", "#C2B597"
WEALTH_STOPS = ["#9C5B3B", "#C89B5A", "#EADFC5", "#7FA6A0", "#3E6B66"]
WEALTH = LinearSegmentedColormap.from_list("wealth", WEALTH_STOPS)
OUTLET_FILL, OUTLET_EDGE = "#8C2E2E", "#3B0D0D"

# OSM highway classes counted as road length (the commerce and urbanity control); paths and
# tracks are walkable but their mapping depends far more on mapper effort.
ROAD_CLASSES = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
                "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
                "residential", "living_street", "service", "road"]

# PCSO's five sales areas (the folders of its outlet map) -> COD-AB region pcodes,
# confirmed by where the map's own points fall.
PCSO_AREAS = {
    "National Capital Region": ["PH13"],
    "Northern and Central Luzon": ["PH14", "PH01", "PH02", "PH03"],
    "Southern Luzon and Bicol Region": ["PH04", "PH17", "PH05"],
    "Visayas": ["PH06", "PH07", "PH08"],
    "Mindanao": ["PH09", "PH10", "PH11", "PH12", "PH16", "PH19"],
}
REGION_TO_AREA = {r: a for a, regions in PCSO_AREAS.items() for r in regions}

METRO_CEBU = ["Cebu City (Capital)", "Lapu-Lapu City (Opon)", "Mandaue City", "City of Talisay",
              "Danao City", "City of Carcar", "City of Naga", "Compostela", "Consolacion",
              "Cordova", "Liloan", "Minglanilla", "San Fernando"]  # the 13 LGUs of Metro Cebu


def metro_of(adm1_pcode, adm2_name, adm3_name):
    """The three city areas the study looks inside, or "Rest of the country"."""
    metro = pd.Series("Rest of the country", index=adm1_pcode.index)
    metro[adm1_pcode == "PH13"] = "Metro Manila"
    metro[(adm2_name == "Cebu") & adm3_name.isin(METRO_CEBU)] = "Metro Cebu"
    metro[adm3_name == "Davao City"] = "Davao City"
    return metro


def quadkey(x, y, z=Z):
    """Bing quadkey of tile (x, y): the RWI's tile id, as a string of z digits."""
    return "".join(str(((x >> (z - i)) & 1) | (((y >> (z - i)) & 1) << 1)) for i in range(1, z + 1))


# lat/lon canvas the wealth grid is painted onto for the maps
CANVAS = dict(lon_min=116.85, lon_max=126.65, lat_min=4.55, lat_max=21.15)


def lonlat_to_tile(lon, lat, z=Z):
    n = 2 ** z
    x = np.floor((lon + 180.0) / 360.0 * n).astype(int)
    y = np.floor((1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n).astype(int)
    return x, y


def tile_bounds(x, y, z=Z):
    """Return (min_lon, min_lat, max_lon, max_lat) for tile (x, y)."""
    n = 2 ** z
    lon1 = x / n * 360.0 - 180.0
    lon2 = (x + 1) / n * 360.0 - 180.0
    lat1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))        # north
    lat2 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))  # south
    return lon1, lat2, lon2, lat1


def weighted_quantiles(values, weights, q):
    """Label each value 0..q-1 so every bin holds about equal total weight (population)."""
    order = np.argsort(values, kind="stable")
    cw = np.cumsum(weights[order]) / weights.sum()
    edges = np.searchsorted(cw, np.linspace(0, 1, q + 1)[1:-1])
    labels = np.zeros(len(values), dtype=int)
    labels[order] = np.digitize(np.arange(len(values)), edges)
    return labels  # 0 = poorest


def read_rwi():
    return pd.read_csv(RAW / "phl_rwi.csv")


def ncr_boundary():
    """Metro Manila (National Capital Region) polygon(s) from GADM level 1."""
    import geopandas as gpd
    adm1 = gpd.read_file(RAW / "gadm41_PHL.gpkg", layer="ADM_ADM_1")
    return adm1[adm1["NAME_1"].str.contains("Manila|National Capital", case=False, na=False)]


def rwi_canvas(res):
    """Paint the RWI onto a regular lat/lon canvas: each pixel takes its zoom-14 tile's RWI."""
    rwi = read_rwi()
    tx, ty = lonlat_to_tile(rwi.longitude.values, rwi.latitude.values)
    lookup = pd.Series(rwi.rwi.values, index=tx.astype(np.int64) * 100000 + ty).groupby(level=0).mean()
    lons = np.arange(CANVAS["lon_min"], CANVAS["lon_max"], res)
    lats = np.arange(CANVAS["lat_max"], CANVAS["lat_min"], -res)  # top-down for image rows
    lon, lat = np.meshgrid(lons, lats)
    px, py = lonlat_to_tile(lon.ravel(), lat.ravel())
    grid = lookup.reindex(px.astype(np.int64) * 100000 + py).values.reshape(lat.shape)
    vmin, vmax = np.nanpercentile(rwi.rwi, 4), np.nanpercentile(rwi.rwi, 96)
    return grid, vmin, vmax
