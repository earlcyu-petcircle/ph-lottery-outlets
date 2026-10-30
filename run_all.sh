#!/usr/bin/env bash
# One command, from a clean clone to every table, number, figure and map.
#   ./run_all.sh              reuse files already in data/raw/
#   ./run_all.sh data         only the data-collection step: the analysis-ready tile and
#                             barangay tables and the data-quality tables in data/derived/
#   ./run_all.sh --refresh    download everything again (new PCSO, OSM and Overture snapshots)
# Creates a local virtual environment in .venv/; installs nothing globally.
# Needs about 1.2 GB of downloads and 8 GB of memory.
set -euo pipefail
cd "$(dirname "$0")"

ONLY_DATA=0
FETCH_ARGS=()
for arg in "$@"; do
  case "$arg" in
    data) ONLY_DATA=1 ;;
    --refresh) FETCH_ARGS+=(--refresh) ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

PYTHON="${PYTHON:-python3.12}"
if [ ! -x .venv/bin/python ]; then
  "$PYTHON" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
fi
.venv/bin/pip install --quiet -r requirements.txt

VENV_PYTHON=.venv/bin/python bash src/fetch_data.sh "${FETCH_ARGS[@]+"${FETCH_ARGS[@]}"}"

# Step 2, data collection: PCSO outlets, people, wealth, shops and roads on tiles and barangays
for step in osm_extract barangays pcso tables; do
  echo "== src/$step.py"
  .venv/bin/python src/$step.py
done
[ "$ONLY_DATA" = 1 ] && exit 0

# Version-1 study (OSM outlets), which the README still reports until steps 3-5 replace it
for step in analysis robustness coverage viz mapfig map; do
  echo "== src/$step.py"
  .venv/bin/python src/$step.py
done
