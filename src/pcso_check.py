#!/usr/bin/env python3
"""
PCSO's published outlet map against the lotto agent counts in PCSO's Annual Report CY2023.

pcso.gov.ph answers scripted requests with HTTP 403, so the annual report cannot be fetched
here. The CY2023 figures in tables.py were read through a search index and have not been
checked against the PDF; the five areas sum to 6,416 while the printed total is 6,494. This
table carries them as "unverified" with the exact figure a person must read off the report,
and nothing is filled in by guess.

Writes results/tables/pcso_cy2023_check.csv.

Run after tables.py:  python src/pcso_check.py
"""
import pandas as pd

from analysis_data import TABLES
from common import DERIVED

SOURCE = "PCSO Annual Report CY2023, table 'Lotto Agents, CY 2023' (lotto agents at 31 December 2023)"

a = pd.read_csv(DERIVED / "quality_by_area.csv")
out = pd.DataFrame({
    "pcso_area": a.pcso_area,
    "map_outlets": a.outlets,
    "map_outlets_placed_in_barangay": a.placed_in_barangay,
    "cy2023_agents_search_index": a.cy2023_agents,
    "map_vs_cy2023": a.map_vs_cy2023,
    "cy2023_agents_from_pdf": pd.NA,  # to be read off the PDF by hand
    "status": "manual: unverified, read the figure off the PDF",
    "figure_needed": [f"{SOURCE}: {area}" if area != "Total" else f"{SOURCE}: printed total (search index: 6,494)"
                      for area in a.pcso_area],
})
out.to_csv(TABLES / "pcso_cy2023_check.csv", index=False)
print(out.to_string(index=False))
