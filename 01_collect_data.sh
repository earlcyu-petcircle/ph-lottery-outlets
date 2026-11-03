#!/usr/bin/env bash
# Phase 1: download every open source into data/raw/ (gitignored).
#   ./01_collect_data.sh             keep files already in data/raw/
#   ./01_collect_data.sh --refresh   download everything again (new PCSO, OSM and Overture snapshots)
# About 1.2 GB. The 18 PSA 2024 census workbooks cannot be fetched by script: download them by
# hand into data/manual/popcen2024/ (docs/data-quality.md lists them) before 02_build_tables.sh.
source "$(dirname "$0")/src/shared/setup.sh"

ARGS=()
for arg in "$@"; do
  case "$arg" in
    --refresh) ARGS+=(--refresh) ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

VENV_PYTHON=.venv/bin/python bash src/01_collect_data/download_sources.sh "${ARGS[@]+"${ARGS[@]}"}"
