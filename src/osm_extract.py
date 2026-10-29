#!/usr/bin/env python3
"""
One pass over the Geofabrik Philippines extract for the two OpenStreetMap layers the
barangay study needs besides the outlets themselves.

  - Retail and food points: every shop=* plus food, drink, pharmacy and market amenities,
    as nodes or as the centre of a mapped building. This is the commerce control and the
    denominator of the mapped-share model.
  - Roads and paths: every highway way, kept as node references and coordinates, for road
    length per barangay and for walking distances to the nearest outlet.

Writes data/work/osm_retail.parquet, data/work/osm_ways.npz and the extract's snapshot
time to data/raw/osm_extract_date.txt.

Run after fetch_data.sh:  python src/osm_extract.py
"""
from array import array

import numpy as np
import osmium
import pandas as pd

from common import RAW, ROAD_CLASSES, WORK

FOOD_AMENITIES = {"restaurant", "fast_food", "cafe", "food_court", "bar", "pub", "biergarten",
                  "ice_cream", "pharmacy", "marketplace"}
NOT_SHOPS = {"no", "vacant", "disused"}
# Highway values that are not usable ways on the ground
NOT_ROADS = {"proposed", "construction", "abandoned", "disused", "razed", "platform",
             "raceway", "bus_stop", "elevator", "corridor", "rest_area", "services"}
NO_WALK = {"motorway", "motorway_link", "trunk_link"}  # trunk roads in PH carry jeepney stops
CLASS_CODE = {c: i for i, c in enumerate(ROAD_CLASSES)}
OTHER_CLASS = len(ROAD_CLASSES)        # paths, tracks, steps and the rest
NO_WALK_FLAG = 100                     # added to the code of ways pedestrians cannot use


def retail_kind(tags):
    shop = tags.get("shop")
    if shop and shop not in NOT_SHOPS:
        return "shop", shop
    amenity = tags.get("amenity")
    if amenity in FOOD_AMENITIES:
        return "amenity", amenity
    return None


retail = []
way_offsets, way_class = array("q", [0]), array("h")
node_ref, node_lon, node_lat = array("q"), array("d"), array("d")

PBF = RAW / "philippines-latest.osm.pbf"
stamp = osmium.io.Reader(str(PBF), osmium.osm.NOTHING).header().get("osmosis_replication_timestamp")
(RAW / "osm_extract_date.txt").write_text(stamp[:10] + "\n")
print(f"Geofabrik extract snapshot: {stamp}")

fp = (osmium.FileProcessor(str(PBF),
                           osmium.osm.NODE | osmium.osm.WAY)
      .with_locations()
      .with_filter(osmium.filter.KeyFilter("shop", "amenity", "highway")))
for obj in fp:
    tags = obj.tags
    if obj.is_node():
        kind = retail_kind(tags)
        if kind:
            retail.append(("n", obj.id, obj.location.lon, obj.location.lat, *kind, tags.get("name", "")))
        continue
    # ways
    kind = retail_kind(tags)
    if kind:
        locs = [(n.location.lon, n.location.lat) for n in obj.nodes if n.location.valid()]
        if locs:
            lon, lat = np.mean(locs, axis=0)
            retail.append(("w", obj.id, lon, lat, *kind, tags.get("name", "")))
    hw = tags.get("highway")
    if hw is None or hw in NOT_ROADS or tags.get("area") == "yes":
        continue
    code = CLASS_CODE.get(hw, OTHER_CLASS)
    if hw in NO_WALK or tags.get("foot") == "no" or tags.get("access") == "private":
        code += NO_WALK_FLAG
    n = 0
    for nd in obj.nodes:
        if nd.location.valid():
            node_ref.append(nd.ref)
            node_lon.append(nd.location.lon)
            node_lat.append(nd.location.lat)
            n += 1
    if n >= 2:
        way_offsets.append(len(node_ref))
        way_class.append(code)
    else:  # drop a way with fewer than two located nodes
        del node_ref[len(node_ref) - n:]
        del node_lon[len(node_lon) - n:]
        del node_lat[len(node_lat) - n:]

rdf = pd.DataFrame(retail, columns=["osm_type", "osm_id", "lon", "lat", "key", "value", "name"])
rdf = rdf.sort_values(["osm_type", "osm_id"]).reset_index(drop=True)
rdf.to_parquet(WORK / "osm_retail.parquet", index=False)
np.savez(WORK / "osm_ways.npz", offsets=np.frombuffer(way_offsets, dtype=np.int64),
         cls=np.frombuffer(way_class, dtype=np.int16), ref=np.frombuffer(node_ref, dtype=np.int64),
         lon=np.frombuffer(node_lon), lat=np.frombuffer(node_lat))
print(f"OSM retail and food points: {len(rdf):,} "
      f"(shops {int((rdf.key == 'shop').sum()):,}, food and pharmacy {int((rdf.key == 'amenity').sum()):,})")
print(f"OSM highway ways: {len(way_class):,}   way nodes: {len(node_ref):,}")
