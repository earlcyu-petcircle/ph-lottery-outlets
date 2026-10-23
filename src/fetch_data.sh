#!/usr/bin/env bash
# Download the four open datasets into data/raw/.
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

# Record when the outlets were pulled; the paper quotes this date.
if [ ! -s "$RAW/pull_date.txt" ] || [ "$REFRESH" = 1 ]; then
  date -u +%Y-%m-%d > "$RAW/pull_date.txt"
fi
ls -la "$RAW"
