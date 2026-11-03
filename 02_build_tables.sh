#!/usr/bin/env bash
# Phase 2: build the analysis-ready tables from data/raw/ and the hand-downloaded census.
# Writes data/derived/tiles.csv, barangays.csv and the data-quality tables (committed), and the
# large intermediates in data/work/ (gitignored) that phases 3 and 4 read. About 2 minutes.
source "$(dirname "$0")/src/shared/setup.sh"

require_inputs ./01_collect_data.sh data/raw/pcso_outlets.kml data/raw/phl_rwi.csv \
  data/raw/phl_pop_2024_100m.tif data/raw/ghs_smod_e2025_1km.zip data/raw/phl_admin_boundaries.gdb.zip \
  data/raw/philippines-latest.osm.pbf data/raw/overture_places_ph.parquet
require_inputs "the manual census download in docs/data-quality.md (Getting the files)" data/manual/popcen2024

for step in read_census_2024 extract_osm_shops_and_roads build_barangays place_pcso_outlets build_tables; do
  run_python src/02_build_tables/$step.py
done
