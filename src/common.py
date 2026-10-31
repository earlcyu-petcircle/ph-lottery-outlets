"""
Shared paths, grid helpers and area lookups for the pipeline.

The main unit is the Web-Mercator (Bing/OSM) tile grid at zoom 14, about 2.4 km cells
at Philippine latitudes, which is the native grid of the Meta Relative Wealth Index.
Cells are keyed by integer tile indices (tx, ty), so points go onto tiles without a
spatial join.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"          # downloads from fetch_data.sh (gitignored)
WORK = ROOT / "data" / "work"        # large intermediates (gitignored)
DERIVED = ROOT / "data" / "derived"  # small tables the paper cites (committed)
for _d in (WORK, DERIVED):
    _d.mkdir(parents=True, exist_ok=True)

Z = 14  # RWI native zoom level

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


def lonlat_to_tile(lon, lat, z=Z):
    n = 2 ** z
    x = np.floor((lon + 180.0) / 360.0 * n).astype(int)
    y = np.floor((1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n).astype(int)
    return x, y


def read_rwi():
    return pd.read_csv(RAW / "phl_rwi.csv")

