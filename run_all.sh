#!/usr/bin/env bash
# One command, from a clean clone to every number, figure and map in the paper.
#   ./run_all.sh            reuse files already in data/raw/
#   ./run_all.sh --refresh  download everything again (new OpenStreetMap snapshot)
# Creates a local virtual environment in .venv/; installs nothing globally.
# Needs about 1.1 GB of downloads and 4 GB of memory; a full run takes about 10 minutes.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3.12}"
if [ ! -x .venv/bin/python ]; then
  "$PYTHON" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
fi
.venv/bin/pip install --quiet -r requirements.txt

VENV_PYTHON=.venv/bin/python bash src/fetch_data.sh "$@"

# Tile-level study (the first version, now the MAUP check), then the barangay redesign
for step in analysis robustness coverage viz mapfig map \
            osm_extract outlets barangays barangay_models cities access fig_models; do
  echo "== src/$step.py"
  .venv/bin/python src/$step.py
done
