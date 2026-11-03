#!/usr/bin/env python3
"""
The outcome: PCSO's published map of traditional lotto outlets.

The PCSO outlet page (pcso.gov.ph/Maps/Outlets.aspx) embeds a public Google My Maps layer
whose KML export lists every outlet with its address, PCSO area and a free-text GPS field.
This script parses the GPS text, places each outlet in a barangay, checks the placement
against the address, and places outlets without usable coordinates from their address text
alone (offline: the addresses carry some owners' names, so they are not sent to any
geocoding service).

Placement, in order:
  1. coordinates that parse and fall in or within 1 km of a barangay -> that barangay;
     checked against the cities and municipalities ("towns") named in the address:
       gps_consistent      the point's own town is named;
       gps_other_town      another town is named, and the point is within 10 km of it;
       gps_far             the towns named are all more than 10 km from the point;
       gps_town_unnamed    no town in the outlet's PCSO area could be read from the address;
  2. no usable coordinates -> the barangay named in the address, inside the town named in
     the address, inside the outlet's PCSO area (address_barangay); the outlet is put at
     the barangay's population-weighted centre;
  3. only the town could be read -> the town's population-weighted centre (address_town);
     build_tables.py counts these on tiles but keeps them apart from the main count;
  4. otherwise unplaced (unplaced_town_ambiguous when several towns fit, else unplaced).

Writes data/work/pcso_outlets.parquet (no addresses or names; gitignored) and the
committed summary data/derived/pcso_geocoding.json. The raw KML is never committed.

Run after build_barangays.py:  python src/02_build_tables/place_pcso_outlets.py
"""
import json
import re
import unicodedata
import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))  # shared helpers in src/shared/

from common import DERIVED, PCSO_AREAS, RAW, WORK

KML = "{http://www.opengis.net/kml/2.2}"
UTM = "EPSG:32651"
BOX = dict(lat_min=4.2, lat_max=21.5, lon_min=116.0, lon_max=127.5)
FAR_KM = 10.0

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
assert set(out.area) == set(PCSO_AREAS), sorted(set(out.area))
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


def in_box(lat, lon):
    return BOX["lat_min"] <= lat <= BOX["lat_max"] and BOX["lon_min"] <= lon <= BOX["lon_max"]


def undotted(s, is_lon):
    """A degree value whose decimal point was lost: "1210123" -> 121.0123, "143210" -> 14.321."""
    if "." in s:
        return float(s)
    k = 3 if is_lon else (1 if s[0] in "456789" else 2)
    return float(s[:k] + "." + s[k:])


def repair_decimal(t):
    """Two decimal degrees with an odd separator ("14.5-121.0", "14.5 : 121.0", "14.5 LONG 121.0",
    "9.123456.123.456789") or with one decimal point lost; None if the text is not that."""
    if re.search(r"['\"°]|\d\s*[NSEW]\b", t, re.I):
        return None  # degree-minute-second text, not decimal
    t = re.sub(r"(\d)\.(\d{3}\.\d)", r"\1 \2", t)  # two numbers run together with a dot
    t = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", t)  # "121. 0123" -> "121.0123"
    nums = re.findall(r"\d+(?:\.\d+)?", t)
    if len(nums) != 2 or all("." not in n for n in nums):
        return None
    for a, b in (nums, nums[::-1]):
        lat, lon = undotted(a, False), undotted(b, True)
        if in_box(lat, lon):
            return lat, lon
    return None


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
            fixed = repair_decimal(t)
            return (*fixed, "decimal_repaired") if fixed else (None, None, "malformed")
        lat, lon = dms_part(m.group(1), False), dms_part(m.group(2), True)
        if lat is None or lon is None:
            return None, None, "bad_dms"
        kind = "dms"
    if not in_box(lat, lon):
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
pix["town"] = b.adm3_pcode.values[pix.b]
cen = pix.groupby("b")[["wx", "wy", "pop_census"]].sum()
b["cen_lon"] = (cen.wx / cen.pop_census).reindex(b.index).fillna(b.rp_lon).values
b["cen_lat"] = (cen.wy / cen.pop_census).reindex(b.index).fillna(b.rp_lat).values
tcen = pix.groupby("town")[["wx", "wy", "pop_census"]].sum()
town_cen = pd.DataFrame({"lon": tcen.wx / tcen.pop_census, "lat": tcen.wy / tcen.pop_census})
town_cen = town_cen.combine_first(b.groupby("adm3_pcode")[["rp_lon", "rp_lat"]].mean()
                                  .rename(columns={"rp_lon": "lon", "rp_lat": "lat"}))
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
by_area = {k: b[b.adm1_pcode.isin(v)] for k, v in PCSO_AREAS.items()}
towns_by_area = {k: v.drop_duplicates("adm3_pcode")[["adm3_pcode", "mun_p", "prov_p"]] for k, v in by_area.items()}


def towns_named(i):
    """The towns in the outlet's PCSO area whose name appears in its address."""
    t = towns_by_area[out.at[i, "area"]]
    return t[[m in out.at[i, "addr_n"] for m in t.mun_p.values]]


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
own_named = np.array([m in a for m, a in zip(b.mun_p.values[out.b.clip(lower=0)], out.addr_n)])
out.loc[placed & own_named, "status"] = "gps_consistent"

# Points whose own town is not named: how far are they from the towns that are?
geoms_utm = geoms.to_crs(UTM).geometry.values
out["named_town_km"] = np.nan
for i in out.index[placed & ~own_named]:
    named = towns_named(i)
    if named.empty:
        out.at[i, "status"] = "gps_town_unnamed"
        continue
    p = gpd.GeoSeries([shapely.Point(out.at[i, "lon"], out.at[i, "lat"])], crs=4326).to_crs(UTM).iloc[0]
    cand = np.where(b.adm3_pcode.isin(named.adm3_pcode).values)[0]
    km = float(shapely.distance(geoms_utm[cand], p).min()) / 1000
    out.at[i, "named_town_km"] = km
    out.at[i, "status"] = "gps_other_town" if km <= FAR_KM else "gps_far"

# ---------------------------------------------------------------------------
# 4. Address text -> barangay or town for outlets without usable coordinates
# ---------------------------------------------------------------------------
def brgy_in(addr, phrase):
    core = phrase.strip()
    if not core:
        return False
    if core.isdigit():  # numbered barangays need the word barangay in front
        return re.search(rf" (brgy|barangay|bgy|brg) (no )?{core} ", addr) is not None
    return phrase in addr


out["town_pcode"] = None
for i in out.index[out.status.isin(["no_coordinates", "coordinates_off_land"])]:
    addr, muns = out.at[i, "addr_n"], towns_named(i)
    if muns.empty:
        out.at[i, "status"] = "unplaced"
        continue
    if len(muns) > 1:  # several towns named: prefer one whose province is named too
        with_prov = muns[[p in addr for p in muns.prov_p.values]]
        muns = with_prov if not with_prov.empty else muns
        muns = muns[muns.mun_p.str.len() == muns.mun_p.str.len().max()]
    if len(muns) > 1:
        out.at[i, "status"] = "unplaced_town_ambiguous"
        continue
    town = muns.adm3_pcode.iloc[0]
    out.at[i, "town_pcode"] = town
    cand = b[b.adm3_pcode == town]
    hits = cand[[brgy_in(addr, p) for p in cand.brgy_p.values]]
    if hits.empty:
        out.at[i, "status"] = "address_town"
        out.at[i, "lon"], out.at[i, "lat"] = town_cen.at[town, "lon"], town_cen.at[town, "lat"]
        continue
    hit = hits.loc[hits.brgy_p.str.len().idxmax()]
    out.at[i, "b"] = int(hit.name)
    out.at[i, "lon"], out.at[i, "lat"] = hit.cen_lon, hit.cen_lat
    out.at[i, "status"] = "address_barangay"

# ---------------------------------------------------------------------------
# 5. Save (no addresses) and summarise
# ---------------------------------------------------------------------------
out["placed"] = out.b >= 0  # in a barangay: gps_* and address_barangay
out.loc[out.status.str.startswith("unplaced"), ["lon", "lat"]] = np.nan  # drop off-land points
out["adm4_pcode"] = np.where(out.placed, b.adm4_pcode.values[out.b.clip(lower=0)], None)
out["adm1_pcode"] = np.where(out.placed, b.adm1_pcode.values[out.b.clip(lower=0)], None)
out.loc[out.status == "address_town", "adm1_pcode"] = out.town_pcode.str[:4]
out[["area", "coord_kind", "status", "placed", "named_town_km", "lon", "lat", "b", "adm4_pcode",
     "adm1_pcode", "town_pcode"]].to_parquet(WORK / "pcso_outlets.parquet", index=False)

summary = {
    "outlets": int(len(out)),
    "pull_date": (RAW / "pcso_pull_date.txt").read_text().strip(),
    "duplicate_addresses": int(out.address.duplicated().sum()),
    "coordinate_parse": {k: int(v) for k, v in out.coord_kind.value_counts().items()},
    "status": {k: int(v) for k, v in out.status.value_counts().items()},
    "placed_in_barangay": int(out.placed.sum()),
    "placed_share": float(f"{out.placed.mean():.4g}"),
}
with open(DERIVED / "pcso_geocoding.json", "w") as fh:
    json.dump(summary, fh, indent=2)
    fh.write("\n")
print(json.dumps(summary, indent=2))
