#!/usr/bin/env bash
# One command, from a clean clone to every number, figure and map in the paper.
#   ./run_all.sh            reuse files already in data/raw/
#   ./run_all.sh --refresh  download everything again (new OpenStreetMap snapshot)
# Creates a local virtual environment in .venv/; installs nothing globally.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3.12}"
if [ ! -x .venv/bin/python ]; then
  "$PYTHON" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
fi
.venv/bin/pip install --quiet -r requirements.txt

bash src/fetch_data.sh "$@"

for step in analysis robustness coverage viz mapfig map; do
  echo "== src/$step.py"
  .venv/bin/python src/$step.py
done
