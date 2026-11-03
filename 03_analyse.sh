#!/usr/bin/env bash
# Phase 3: the data analysis, as five narrative notebooks in notebooks/, executed in order:
#   01_descriptives                 outlets per 100,000 by wealth quintile, PCSO CY2023 check
#   02_count_and_presence_models    national NB2 count and presence models, spatial checks
#   03_within_cities                the same inside Metro Manila (NCR), Metro Cebu and Metro Davao,
#                                   side by side with the national results
#   04_road_distance                road distance to the nearest outlet by wealth quintile
#   05_maps                         static choropleth maps of outlet density beside wealth
# The notebooks import their logic from src/02_data_analysis/ and are saved with their outputs
# by src/shared/run_notebook.py, which merges each cell's printed output into one stream so a
# rerun saves the same file.
# Writes results/tables/ and results/figures/ (committed) and the model residuals the web map
# uses to data/work/. About 10 minutes.
source "$(dirname "$0")/src/shared/setup.sh"

require_inputs ./02_build_tables.sh data/derived/tiles.csv data/derived/barangays.csv \
  data/derived/quality_by_area.csv data/work/pcso_outlets.parquet data/work/pixels.parquet \
  data/work/osm_ways.npz data/work/barangay_geoms.parquet

for nb in 01_descriptives 02_count_and_presence_models 03_within_cities 04_road_distance 05_maps; do
  echo "== notebooks/$nb.ipynb"
  .venv/bin/python src/shared/run_notebook.py "notebooks/$nb.ipynb"
done
