#!/usr/bin/env bash
# Download the open datasets into data/raw/ (gitignored).
# No API keys, no logins, no proprietary data. Run from the repo root.
# Files that already exist are kept; pass --refresh to download everything again
# (the PCSO map, OpenStreetMap and Overture change over time, so a refresh can change counts).
# About 1.2 GB in all; the Geofabrik extract and the COD-AB geodatabase are most of it.
set -euo pipefail

RAW="data/raw"
UA="ph-lottery-outlets/1.0 (open-data spatial research; https://github.com/earlcyu-petcircle/ph-lottery-outlets)"
REFRESH=0
[ "${1:-}" = "--refresh" ] && REFRESH=1
mkdir -p "$RAW"

fetch() {  # fetch <output file> <curl args...>
  local out="$RAW/$1"; shift
  if [ -s "$out" ] && [ "$REFRESH" = 0 ]; then
    echo "keep     $out"
    return
  fi
  echo "download $out"
  curl -fsSL --retry 5 --retry-all-errors -H "User-Agent: $UA" "$@" -o "$out.part"
  mv "$out.part" "$out"
}

stamp() {  # stamp <file>: record the UTC date a moving source was pulled
  if [ ! -s "$RAW/$1" ] || [ "$REFRESH" = 1 ]; then
    date -u +%Y-%m-%d > "$RAW/$1"
  fi
}

# --- Outcome --------------------------------------------------------------------------

# 1. PCSO "Traditional Lotto Outlets": the Google My Maps layer embedded in
#    https://www.pcso.gov.ph/Maps/Outlets.aspx, exported as KML. Every outlet's address,
#    PCSO area and free-text GPS field; parsed by src/pcso.py. The addresses can carry
#    owners' names, so this file is never committed.
fetch pcso_outlets.kml --max-time 300 \
  "https://www.google.com/maps/d/kml?mid=1dCEzj5MVaZkS5OPjPhaaQXVl-uSDAG0&forcekml=1"
stamp pcso_pull_date.txt

# --- Wealth ---------------------------------------------------------------------------

# 2. Meta Relative Wealth Index, Philippines (HDX): one row per 2.4 km tile, with its error.
fetch phl_rwi.csv --max-time 120 \
  "https://data.humdata.org/dataset/76f2a2ea-ba50-40f5-b79c-db95d668b843/resource/62233330-20a8-4623-ad87-429b22409ed5/download/phl_relative_wealth_index.csv"

# --- Population -----------------------------------------------------------------------

# 3. WorldPop R2025A 2024, 100 m, constrained to built settlement. Only its spatial pattern
#    is used: census counts are spread over its pixels inside each barangay.
fetch phl_pop_2024_100m.tif --max-time 900 \
  "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2024/PHL/v1/100m/constrained/phl_pop_2024_CN_100m_R2025A_v1.tif"

# 4. Census population by barangay: PSA 2024 Census of Population (POPCEN), official under
#    Proclamation No. 973. psa.gov.ph answers scripts with a bot check, so the 18 regional
#    "Table C - Population by Barangay" workbooks are downloaded by hand into
#    data/manual/popcen2024/ (gitignored); src/popcen2024.py reads them and names any missing.

# 5. GHSL Degree of Urbanisation (JRC GHS-SMOD R2023A, 2025 epoch, 1 km, Mollweide), for the
#    share of people living in urban centres and urban clusters.
fetch ghs_smod_e2025_1km.zip --max-time 900 \
  "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000/V2-0/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.zip"

# --- Boundaries and codes -------------------------------------------------------------

# 6. OCHA COD-AB Philippines v03 (HDX): region to barangay polygons with PSGC-based pcodes.
fetch phl_admin_boundaries.gdb.zip --max-time 1800 \
  "https://data.humdata.org/dataset/caf116df-f984-4deb-85ca-41b349d3f313/resource/3fa0dbcf-e07d-4506-9821-ba15baa6da07/download/phl_admin_boundaries.gdb.zip"

# --- Commerce and roads ---------------------------------------------------------------

# 7. Every OpenStreetMap feature: Geofabrik Philippines extract (about 600 MB), for shop
#    points and roads. Geofabrik replaces it daily; src/osm_extract.py records its snapshot.
fetch philippines-latest.osm.pbf --max-time 3600 \
  "https://download.geofabrik.de/asia/philippines-latest.osm.pbf"

# 8. Overture Maps places in the Philippine bounding box (slim columns), read from the
#    public S3 release with DuckDB; see src/fetch_overture.py.
if [ ! -s "$RAW/overture_places_ph.parquet" ] || [ "$REFRESH" = 1 ]; then
  echo "download $RAW/overture_places_ph.parquet"
  "${VENV_PYTHON:-.venv/bin/python}" src/fetch_overture.py "$RAW/overture_places_ph.parquet"
else
  echo "keep     $RAW/overture_places_ph.parquet"
fi

ls -la "$RAW"
