#!/usr/bin/env python3
"""
Write docs/map/palette.js, the web map's colours, from src/shared/map_layers.py, so the web map
and the static maps share one palette (the Atlas data palette in src/shared/atlas.py).

The map tiles carry each unit's classes, not colours, so a palette change needs only this file,
not new tiles. Run by 04_build_map.sh; also runs on its own:
  .venv/bin/python src/04_build_map/write_web_palette.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

import map_layers as ml

OUT = Path(__file__).resolve().parents[2] / "docs" / "map" / "palette.js"

PALETTE = {
    "RATE": [ml.RATE_NONE, *ml.RATE],  # no outlet, then five rate classes
    "RWI": ml.RWI,
    "BIV": ml.BIV,
    "LISA": ml.LISA,
}

lines = ["// Written by src/04_build_map/write_web_palette.py from src/shared/map_layers.py; do not edit."]
lines += [f"const {name} = {json.dumps(value)};" for name, value in PALETTE.items()]
OUT.write_text("\n".join(lines) + "\n")
print(f"wrote {OUT.relative_to(OUT.parents[2])}")
