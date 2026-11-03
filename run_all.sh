#!/usr/bin/env bash
# Every phase in order, from a clean clone to the tables, results and web map:
#   ./run_all.sh              reuse files already in data/raw/
#   ./run_all.sh --refresh    download everything again (new PCSO, OSM and Overture snapshots)
# Each phase also runs on its own, from the outputs of the one before:
#   ./01_collect_data.sh   downloads into data/raw/
#   ./02_build_tables.sh   tile and barangay tables in data/derived/ (about 2 minutes)
#   ./03_analyse.sh        models, distances and charts in results/ (about 10 minutes)
#   ./04_build_map.sh      web map tiles in docs/map/data/
# Needs Python 3.12, curl, tippecanoe (brew install tippecanoe), about 1.2 GB of downloads,
# 5 GB of memory, and the 18 PSA 2024 census workbooks downloaded by hand into
# data/manual/popcen2024/ (docs/data-quality.md lists them).
set -euo pipefail
cd "$(dirname "$0")"
source src/shared/setup.sh
require_tippecanoe  # checked up front so a long run does not stop at the last phase

./01_collect_data.sh "$@"
./02_build_tables.sh
./03_analyse.sh
./04_build_map.sh
