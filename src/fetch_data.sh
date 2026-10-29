#!/usr/bin/env bash
# Download the open datasets into data/raw/.
# No API keys, no logins, no proprietary data. Run from the repo root.
# Files that already exist are kept; pass --refresh to download everything again
# (OpenStreetMap changes daily, so a refresh can change the outlet count).
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

# 1. Lottery outlets: OpenStreetMap via the Overpass API.
#    Overpass refuses requests without a User-Agent (HTTP 406).
fetch osm_lottery_ph.json --max-time 300 \
  --data-urlencode "data@src/overpass_query.ql" \
  "https://overpass-api.de/api/interpreter"

# 2. Neighbourhood wealth: Meta Relative Wealth Index (Philippines) via HDX.
fetch phl_rwi.csv --max-time 120 \
  "https://data.humdata.org/dataset/76f2a2ea-ba50-40f5-b79c-db95d668b843/resource/62233330-20a8-4623-ad87-429b22409ed5/download/phl_relative_wealth_index.csv"

# 3. Population: WorldPop 2020 UN-adjusted 1 km population count.
fetch phl_pop_1km.tif --max-time 300 \
  "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/PHL/phl_ppp_2020_1km_Aggregated_UNadj.tif"

# 4. Administrative boundaries: GADM 4.1 Philippines (all levels, GeoPackage).
fetch gadm41_PHL.gpkg --max-time 600 \
  "https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_PHL.gpkg"

# 5. Barangay boundaries with PSGC codes: OCHA COD-AB Philippines (HDX), file geodatabase.
fetch phl_admin_boundaries.gdb.zip --max-time 1800 \
  "https://data.humdata.org/dataset/caf116df-f984-4deb-85ca-41b349d3f313/resource/3fa0dbcf-e07d-4506-9821-ba15baa6da07/download/phl_admin_boundaries.gdb.zip"

# 6. 2020 census population by barangay, 10-digit PSGC (OCHA Philippines, HDX).
fetch phl_census2020_brgy_pop.xlsx --max-time 300 \
  "https://data.humdata.org/dataset/186f5609-e970-4165-86a0-a87a770532e2/resource/dd6fb33a-a91b-450c-a0f8-0b760a75458e/download/2020-census-total-popn-brgy_adm4_new-pcode.xlsx"

# 7. Population at 100 m: WorldPop 2020 UN-adjusted, constrained to built settlement.
#    Used to weight wealth inside barangays and as origins for the access distances.
fetch phl_pop_100m.tif --max-time 600 \
  "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/PHL/phl_ppp_2020_UNadj_constrained.tif"

# 8. Every OpenStreetMap feature (shops, food, roads): Geofabrik Philippines extract, about 600 MB.
#    Geofabrik replaces this file daily; src/osm_extract.py reads its snapshot time from the header.
fetch philippines-latest.osm.pbf --max-time 3600 \
  "https://download.geofabrik.de/asia/philippines-latest.osm.pbf"

# 9. Overture Maps places in the Philippine bounding box (slim columns), read from the
#    public S3 release with DuckDB; see src/fetch_overture.py.
if [ ! -s "$RAW/overture_places_ph.parquet" ] || [ "$REFRESH" = 1 ]; then
  echo "download $RAW/overture_places_ph.parquet"
  "${VENV_PYTHON:-.venv/bin/python}" src/fetch_overture.py "$RAW/overture_places_ph.parquet"
else
  echo "keep     $RAW/overture_places_ph.parquet"
fi

# 10. PSA 2021 city and municipal poverty estimates cannot be fetched automatically
#     (psa.gov.ph answers scripts with a Cloudflare bot check). See docs/psa-poverty-data.md
#     for the manual step; the pipeline runs without it and says so.
[ -s data/manual/psa_sae_2021.csv ] || echo "missing  data/manual/psa_sae_2021.csv (optional, manual: docs/psa-poverty-data.md)"

# Record when the outlets were pulled; the paper quotes this date.
if [ ! -s "$RAW/pull_date.txt" ] || [ "$REFRESH" = 1 ]; then
  date -u +%Y-%m-%d > "$RAW/pull_date.txt"
fi
ls -la "$RAW"
