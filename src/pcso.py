#!/usr/bin/env python3
"""
The outcome: PCSO's published map of traditional lotto outlets.

The PCSO outlet page (pcso.gov.ph/Maps/Outlets.aspx) embeds a public Google My Maps layer
whose KML export lists every outlet with its address, PCSO area and a free-text GPS field.
This script parses the GPS text, places each outlet in a barangay, checks the placement
against the address, and matches outlets without usable coordinates to a barangay from
their address text alone (offline: the addresses carry some owners' names, so they are
not sent to any geocoding service).

Placement, in order:
  1. coordinates that parse and fall in or within 1 km of a barangay -> that barangay;
     flagged "consistent" if the barangay's city or municipality is named in the address;
  2. no usable coordinates -> the barangay named in the address, within the city or
     municipality named in the address, inside the outlet's PCSO area; the outlet is put at
     the barangay's population-weighted centre;
  3. otherwise the outlet is reported as unplaced (with the city or municipality when only
     that could be read).

Writes data/work/pcso_outlets.parquet (no addresses or names; gitignored) and the
committed summary data/derived/pcso_geocoding.json. The raw KML is never committed.

Run after barangays.py:  python src/pcso.py
"""
import json
import re
import unicodedata
import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from common import DERIVED, RAW, WORK

KML = "{http://www.opengis.net/kml/2.2}"
UTM = "EPSG:32651"
AREA_REGIONS = {  # PCSO area folder -> COD-AB region codes, confirmed by where the points fall
    "National Capital Region": ["PH13"],
    "Northern and Central Luzon": ["PH14", "PH01", "PH02", "PH03"],
    "Southern Luzon and Bicol Region": ["PH04", "PH17", "PH05"],
    "Visayas": ["PH06", "PH07", "PH08"],
    "Mindanao": ["PH09", "PH10", "PH11", "PH12", "PH16", "PH19"],
}
BOX = dict(lat_min=4.2, lat_max=21.5, lon_min=116.0, lon_max=127.5)


# ---------------------------------------------------------------------------
# 1. Parse the KML
# ---------------------------------------------------------------------------
rows = []
for folder in ET.parse(RAW / "pcso_outlets.kml").getroot().iter(KML + "Folder"):
    area = folder.find(KML + "name").text
    for pm in folder.findall(KML + "Placemark"):
        data = {d.get("name"): (d.findtext(KML + "value") or "") for d in pm.iter(KML + "Data")}
        addr = pm.findtext(KML + "address") or pm.findtext(KML + "name") or ""
        rows.append({"area": area, "address": addr, "gps": data.get("GPSCoordinates", "")})
out = pd.DataFrame(rows)
assert set(out.area) == set(AREA_REGIONS), sorted(set(out.area))
print(f"PCSO outlets in the KML: {len(out):,}")


def dms_part(s, is_lon):
    """One degree-minute-second coordinate, tolerating the lost degree sign of the export."""
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if len(nums) >= 3:
        d, m, sec = map(float, nums[:3])
    elif len(nums) == 2:  # "12329'14.42" -> 123 deg 29 min 14.42 s
        a, sec = nums[0], float(nums[1])
        k = 3 if is_lon else max(1, len(a) - 2)
        d, m = (float(a), 0.0) if len(a) <= k else (float(a[:k]), float(a[k:]))
    elif len(nums) == 1 and "." not in nums[0]:  # degree-minute only: "1640'N"
        a = nums[0]
        k = 3 if is_lon else max(1, len(a) - 2)
        d, m, sec = float(a[:k]), float(a[k:] or 0), 0.0
    else:
        return float(nums[0]) if nums else None
    return None if m >= 60 or sec >= 60 else d + m / 60 + sec / 3600


DEC = re.compile(r"^\s*(-?\d{1,3}\.\d+)\s*[,;/ ]+\s*(-?\d{1,3}\.\d+)\s*$")
DMS = re.compile(r"^(.*?[NS])\s*[,/]?\s*(.*?[EW])\s*$", re.I)


def parse_gps(text):
    """(lat, lon, kind) or (None, None, reason)."""
    t = (text or "").strip()
    if not t:
        return None, None, "blank"
    m = DEC.match(t)
    if m:
        a, b = abs(float(m.group(1))), abs(float(m.group(2)))
        lat, lon = (a, b) if a < b else (b, a)  # swap a reversed pair
        kind = "decimal"
    else:
        m = DMS.match(t)
        if not m:
            return None, None, "malformed"
        lat, lon = dms_part(m.group(1), False), dms_part(m.group(2), True)
        if lat is None or lon is None:
            return None, None, "bad_dms"
        kind = "dms"
    if not (BOX["lat_min"] <= lat <= BOX["lat_max"] and BOX["lon_min"] <= lon <= BOX["lon_max"]):
        return None, None, "out_of_range"
    return lat, lon, kind


parsed = [parse_gps(g) for g in out.gps]
out["lat"] = [p[0] for p in parsed]
out["lon"] = [p[1] for p in parsed]
out["coord_kind"] = [p[2] for p in parsed]

# ---------------------------------------------------------------------------
# 2. Barangays, names and population-weighted centres
# ---------------------------------------------------------------------------
b = pd.read_parquet(WORK / "barangays.parquet")
geoms = gpd.read_parquet(WORK / "barangay_geoms.parquet")
assert (geoms.adm4_pcode.values == b.adm4_pcode.values).all()
pix = pd.read_parquet(WORK / "pixels.parquet", columns=["lon", "lat", "pop_census", "b"])
pix["wx"], pix["wy"] = pix.lon * pix.pop_census, pix.lat * pix.pop_census
cen = pix.groupby("b")[["wx", "wy", "pop_census"]].sum()
b["cen_lon"] = (cen.wx / cen.pop_census).reindex(b.index).fillna(b.rp_lon).values
b["cen_lat"] = (cen.wy / cen.pop_census).reindex(b.index).fillna(b.rp_lat).values
del pix


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\bsta\b\.?", "santa", re.sub(r"\bsto\b\.?", "santo", s))
    return " " + re.sub(r"[^a-z0-9]+", " ", s).strip() + " "


def mun_phrase(name):
    s = re.sub(r"\(.*?\)|\bcity of\b|\bcity\b", " ", unicodedata.normalize("NFKD", name)
               .encode("ascii", "ignore").decode().lower())
    return norm(s)


def brgy_phrase(name):
    s = re.sub(r"\(.*?\)|\bpoblacion\b|\bpob\b\.?|\bbarangay\b|\bbrgy\b|\bbgy\b", " ",
               unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower())
    return norm(s)


b["mun_p"] = b.adm3_name.map(mun_phrase)
b["brgy_p"] = b.adm4_name.map(brgy_phrase)
b["prov_p"] = b.adm2_name.map(mun_phrase)
out["addr_n"] = out.address.map(norm)

# ---------------------------------------------------------------------------
# 3. Coordinates -> barangay, and the address check
# ---------------------------------------------------------------------------
tree = shapely.STRtree(geoms.geometry.values)
has = out.lat.notna().values
pts = shapely.points(out.lon.values[has], out.lat.values[has])
qi, qb = tree.query(pts, predicate="intersects")
keep = ~pd.Series(qi).duplicated().values
bi = np.full(has.sum(), -1)
bi[qi[keep]] = qb[keep]
miss = np.where(bi < 0)[0]
if len(miss):  # just offshore: nearest barangay within 1 km
    g = gpd.GeoDataFrame(geometry=[pts[i] for i in miss], crs=4326).to_crs(UTM)
    j = gpd.sjoin_nearest(g, geoms[["geometry"]].to_crs(UTM), how="left", max_distance=1000)
    bi[miss] = j[~j.index.duplicated()]["index_right"].fillna(-1).astype(int).values
out["b"] = -1
out.loc[has, "b"] = bi
placed = out.b >= 0
out["status"] = np.where(~has, "no_coordinates", np.where(placed, "", "coordinates_off_land"))
mun_named = [m in a for m, a in zip(b.mun_p.values[out.b.where(placed, 0)], out.addr_n)]
out.loc[placed, "status"] = np.where(np.array(mun_named)[placed.values], "coordinates_consistent",
                                     "coordinates_other_municipality")

# ---------------------------------------------------------------------------
# 4. Address text -> barangay for outlets without usable coordinates
# ---------------------------------------------------------------------------
def brgy_in(addr, phrase):
    core = phrase.strip()
    if not core:
        return False
    if core.isdigit():  # numbered barangays need the word barangay in front
        return re.search(rf" (brgy|barangay|bgy|brg) (no )?{core} ", addr) is not None
    return phrase in addr


by_region = {k: b[b.adm1_pcode.isin(v)] for k, v in AREA_REGIONS.items()}
todo = out.index[out.status.isin(["no_coordinates", "coordinates_off_land"])]
for i in todo:
    addr, cand = out.at[i, "addr_n"], by_region[out.at[i, "area"]]
    muns = cand[[m in addr for m in cand.mun_p.values]]
    if muns.empty:
        out.at[i, "status"] = "unplaced"
        continue
    if muns.adm3_pcode.nunique() > 1:  # several towns named: prefer one whose province is named too
        with_prov = muns[[p in addr for p in muns.prov_p.values]]
        muns = with_prov if not with_prov.empty else muns
        longest = muns.mun_p.str.len().max()
        muns = muns[muns.mun_p.str.len() == longest]
    if muns.adm3_pcode.nunique() > 1:
        out.at[i, "status"] = "unplaced_town_ambiguous"
        continue
    hits = muns[[brgy_in(addr, p) for p in muns.brgy_p.values]]
    if hits.empty:
        out.at[i, "status"] = "unplaced_town_only"
        out.at[i, "town_pcode"] = muns.adm3_pcode.iloc[0]
        continue
    hit = hits.loc[hits.brgy_p.str.len().idxmax()]
    out.at[i, "b"] = int(hit.name)
    out.at[i, "lon"], out.at[i, "lat"] = hit.cen_lon, hit.cen_lat
    out.at[i, "status"] = "address_barangay"

# ---------------------------------------------------------------------------
# 5. Save (no addresses) and summarise
# ---------------------------------------------------------------------------
out["placed"] = out.b >= 0
out["adm4_pcode"] = np.where(out.placed, b.adm4_pcode.values[out.b.clip(lower=0)], None)
out["adm1_name"] = np.where(out.placed, b.adm1_name.values[out.b.clip(lower=0)], None)
out[["area", "coord_kind", "status", "placed", "lon", "lat", "b", "adm4_pcode", "adm1_name"]].to_parquet(
    WORK / "pcso_outlets.parquet", index=False)

unplaced = out[~out.placed]
town_region = unplaced.town_pcode.dropna().str[:4].map(
    dict(zip(b.adm1_pcode, b.adm1_name))) if "town_pcode" in out.columns else pd.Series(dtype=str)
summary = {
    "outlets": int(len(out)),
    "duplicate_addresses": int(out.address.duplicated().sum()),
    "coordinate_parse": {k: int(v) for k, v in out.coord_kind.value_counts().items()},
    "status": {k: int(v) for k, v in out.status.value_counts().items()},
    "placed": int(out.placed.sum()),
    "placed_share": float(f"{out.placed.mean():.4g}"),
    "by_area": {a: {"outlets": int(len(g)), "placed": int(g.placed.sum()),
                    "address_barangay": int((g.status == "address_barangay").sum()),
                    "unplaced": int((~g.placed).sum())} for a, g in out.groupby("area")},
    "unplaced_town_only_by_region": {k: int(v) for k, v in town_region.value_counts().items()},
}
with open(DERIVED / "pcso_geocoding.json", "w") as fh:
    json.dump(summary, fh, indent=2)
    fh.write("\n")
print(json.dumps(summary, indent=2))
