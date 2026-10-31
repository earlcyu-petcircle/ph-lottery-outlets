#!/usr/bin/env bash
# One command, from a clean clone to the analysis-ready tables.
#   ./run_all.sh              reuse files already in data/raw/
#   ./run_all.sh --refresh    download everything again (new PCSO, OSM and Overture snapshots)
# Writes the tile and barangay tables and the data-quality tables to data/derived/.
# Creates a local virtual environment in .venv/; installs nothing globally.
# Needs about 1.2 GB of downloads and 5 GB of memory; the table build takes about 2 minutes.
set -euo pipefail
cd "$(dirname "$0")"

FETCH_ARGS=()
for arg in "$@"; do
  case "$arg" in
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

# Data collection: PCSO outlets, people, wealth, shops and roads on tiles and barangays
for step in osm_extract barangays pcso tables; do
  echo "== src/$step.py"
  .venv/bin/python src/$step.py
done
