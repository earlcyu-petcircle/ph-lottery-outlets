#!/usr/bin/env python3
"""
Population by barangay from the PSA 2024 Census of Population (POPCEN), as of 1 July 2024.

psa.gov.ph serves scripts a bot check, so the 18 regional "Table C - Population by Barangay"
workbooks are downloaded by hand into data/manual/popcen2024/ (gitignored; see
docs/data-quality.md). They carry names and counts only: no PSGC codes and no urban flag.

Each workbook has one sheet per province and per highly urbanised city. A sheet starts with
its own total, then stacks one block per city or municipality ("town"), separated by blank
rows: the town's row and total first, then its barangays. The City of Manila sheet stacks its
districts the same way. Notes and sources sit in the first column below the table.

Checks, all reported in data/derived/popcen2024_validation.json and printed:
  - every town total equals the sum of its barangays;
  - every sheet total equals the sum of its towns;
  - NCR's barangays sum to its regional total on the workbook's "Table B" (the only workbook
    that prints one); every other region's sum is reported against nothing it can be checked on;
  - the national sum plus the 1,708 Filipinos counted in Philippine embassies, consulates and
    missions abroad (part of the official count, in no barangay) equals 112,729,484, the
    official count (Proclamation No. 973).

Writes data/work/popcen2024.parquet (one row per barangay: file, province, town, barangay,
population). Run before build_barangays.py:  python src/01_data_collection/read_census_2024.py
"""
import json
import re
import sys
import warnings

import openpyxl
import pandas as pd

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))  # shared helpers in src/shared/

from common import DERIVED, POPCEN_FILES as FILES, ROOT, WORK

FOLDER = ROOT / "data" / "manual" / "popcen2024"
NATIONAL_TOTAL = 112_729_484
# Filipinos in embassies, consulates and missions abroad: in the official total, in no region.
# From the footnote of PSA's 2024 "Table A - Population and APGR by Province and HUC".
MISSIONS_ABROAD = 1_708
FIRST_DATA_ROW = 5  # below the title, date and two header rows


def clean_area(name):
    """A province, city or town name without its footnote marks ("CEBU *", "CARMONA 24")."""
    return re.sub(r"(\s+\d{1,2})?\s*\*?\s*$", "", str(name)).strip()


def blocks_of(ws):
    """Runs of consecutive rows with a name in column B and a number in column D."""
    blocks, cur = [], []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < FIRST_DATA_ROW:
            continue
        name = row[1] if len(row) > 1 else None
        value = row[3] if len(row) > 3 else None
        if name is None or str(name).strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
            continue
        if not isinstance(value, (int, float)):
            raise ValueError(f"{ws.title!r} row {i + 1}: {name!r} has no population ({value!r})")
        cur.append((str(name).strip(), int(value)))
    if cur:
        blocks.append(cur)
    return blocks


missing = [f"{f}.xlsx" for f in FILES if not (FOLDER / f"{f}.xlsx").exists()]
if missing:
    sys.exit(f"popcen2024: missing {len(missing)} of {len(FILES)} workbooks in {FOLDER}: "
             f"{', '.join(missing)}. Download each region's 'Table C - Population by Barangay' "
             "from psa.gov.ph by hand (see docs/data-quality.md).")

warnings.filterwarnings("ignore", module="openpyxl")  # unparseable print headers
rows, problems, sheets, region_check = [], [], [], {}
for file in FILES:
    wb = openpyxl.load_workbook(FOLDER / f"{file}.xlsx", read_only=True)
    seen = {}
    for ws in wb.worksheets:
        if ws.title == "Table B":  # NCR's region, city and municipality table
            for row in ws.iter_rows(values_only=True):
                if row[0] and str(row[0]).startswith("NATIONAL CAPITAL REGION (NCR)") and isinstance(row[5], int):
                    region_check[file] = row[5]  # the 1 July 2024 column
            continue
        blocks = blocks_of(ws)
        if not blocks:
            continue
        head_name, head_total = blocks[0][0]
        if (head_name, head_total) in seen:  # BARMM repeats some sheets under a second name
            continue
        seen[(head_name, head_total)] = ws.title
        sheet_area = clean_area(head_name)
        # A province sheet starts with its total alone; a city sheet is one block, city first
        towns = blocks[1:] if len(blocks[0]) == 1 else blocks
        town_sum = 0
        for block in towns:
            (town_name, town_total), brgys = block[0], block[1:]
            if sum(v for _, v in brgys) != town_total:
                problems.append(f"{file}/{ws.title}: {town_name} total {town_total:,} != "
                                f"barangay sum {sum(v for _, v in brgys):,}")
            town_sum += town_total
            rows += [(file, sheet_area, clean_area(town_name), b, v) for b, v in brgys]
        if town_sum != head_total:
            problems.append(f"{file}/{ws.title}: sheet total {head_total:,} != town sum {town_sum:,}")
        sheets.append({"file": file, "sheet": ws.title, "area": sheet_area, "total": head_total})

pc = pd.DataFrame(rows, columns=["file", "sheet_area", "town", "barangay", "pop"])
by_file = pc.groupby("file")["pop"].sum()
for file, total in region_check.items():
    if by_file[file] != total:
        problems.append(f"{file}: barangay sum {by_file[file]:,} != regional total {total:,}")
national = int(pc["pop"].sum())
if national + MISSIONS_ABROAD != NATIONAL_TOTAL:
    problems.append(f"national sum {national:,} + {MISSIONS_ABROAD:,} abroad != official {NATIONAL_TOTAL:,}")

pc.to_parquet(WORK / "popcen2024.parquet", index=False)
validation = {
    "folder": str(FOLDER.relative_to(ROOT)),
    "workbooks": len(FILES),
    "sheets_read": len(sheets),
    "barangays": int(len(pc)),
    "towns": int(pc[["file", "sheet_area", "town"]].drop_duplicates().shape[0]),
    "national_sum": national,
    "missions_abroad": MISSIONS_ABROAD,
    "national_official": NATIONAL_TOTAL,
    "by_region": {f: int(v) for f, v in by_file.items()},
    "regional_totals_in_workbooks": region_check,
    "problems": problems,
}
with open(DERIVED / "popcen2024_validation.json", "w") as fh:
    json.dump(validation, fh, indent=2)
    fh.write("\n")
print(f"POPCEN 2024: {len(pc):,} barangays in {len(sheets)} sheets, national sum {national:,} "
      f"+ {MISSIONS_ABROAD:,} abroad (official {NATIONAL_TOTAL:,})")
for p in problems:
    print("  MISMATCH:", p)
