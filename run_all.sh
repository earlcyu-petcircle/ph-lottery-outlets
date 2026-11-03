#!/usr/bin/env bash
# One command, from a clean clone to the analysis-ready tables, the step 3 results and the web map.
#   ./run_all.sh                  reuse files already in data/raw/
#   ./run_all.sh --refresh        download everything again (new PCSO, OSM and Overture snapshots)
#   ./run_all.sh --analysis-only  rerun only step 3 (needs data/work/ from an earlier full run)
# Writes the tile and barangay tables and the data-quality tables to data/derived/, the model,
# distance and descriptive tables and two charts to results/, and the web map's vector tiles
# to docs/map/data/ (preview with: .venv/bin/python src/serve_map.py).
# First download the 18 PSA 2024 census workbooks by hand into data/manual/popcen2024/
# (psa.gov.ph blocks scripts); docs/data-quality.md lists them.
# Creates a local virtual environment in .venv/; installs nothing globally. The web map step
# needs tippecanoe (brew install tippecanoe).
# Needs about 1.2 GB of downloads and 5 GB of memory; the table build takes about 2 minutes
# and the analysis about 10 minutes.
set -euo pipefail
cd "$(dirname "$0")"

FETCH_ARGS=()
ANALYSIS_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --refresh) FETCH_ARGS+=(--refresh) ;;
    --analysis-only) ANALYSIS_ONLY=1 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if ! command -v tippecanoe >/dev/null; then
  echo "tippecanoe is needed for the web map: brew install tippecanoe" >&2
  exit 1
fi

PYTHON="${PYTHON:-python3.12}"
if [ ! -x .venv/bin/python ]; then
  "$PYTHON" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
fi
.venv/bin/pip install --quiet -r requirements.txt

if [ "$ANALYSIS_ONLY" = 0 ]; then
  VENV_PYTHON=.venv/bin/python bash src/fetch_data.sh "${FETCH_ARGS[@]+"${FETCH_ARGS[@]}"}"

  # Step 2, data collection: PCSO outlets, people, wealth, shops and roads on tiles and barangays
  for step in popcen2024 osm_extract barangays pcso tables; do
    echo "== src/$step.py"
    .venv/bin/python src/$step.py
  done
fi

# Step 3, data analysis: descriptives, count and presence models with spatial checks, road
# distance, the PCSO CY2023 check, charts and the web map
for step in descriptives models road_distance pcso_check charts webmap; do
  echo "== src/$step.py"
  .venv/bin/python src/$step.py
done
