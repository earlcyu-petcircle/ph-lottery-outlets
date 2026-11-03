#!/usr/bin/env bash
# Phase 4: the web map's vector tiles in docs/map/data/ (PMTiles, built with tippecanoe).
# Outlet points go to docs/map/data/outlets_local.pmtiles for local viewing only (gitignored).
# Preview:  .venv/bin/python src/04_build_map/serve_map.py   then open http://localhost:8000/map/
source "$(dirname "$0")/src/shared/setup.sh"

require_tippecanoe
require_inputs ./02_build_tables.sh data/derived/tiles.csv data/derived/barangays.csv \
  data/work/pcso_outlets.parquet data/work/barangay_geoms.parquet
require_inputs ./03_analyse.sh results/tables/models.csv data/work/residuals_national_tiles.parquet \
  data/work/residuals_ncr_barangays.parquet data/work/residuals_cebu_barangays.parquet \
  data/work/residuals_davao_barangays.parquet

run_python src/04_build_map/build_map_tiles.py
