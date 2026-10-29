#!/usr/bin/env python3
"""
Download a slim extract of every Overture Maps place in the Philippine bounding box.

Reads the public GeoParquet release on S3 directly with DuckDB, filtering on the bbox
struct so only matching row groups are read (no account, no API key). Columns are kept
to what the pipeline needs: point, name, categories, confidence and source datasets.

Usage:  python src/fetch_overture.py data/raw/overture_places_ph.parquet
"""
import sys

import duckdb

RELEASE = "2026-10-21.0"  # the release the earlier Overture scout used
SRC = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=places/type=place/*"

out = sys.argv[1]
con = duckdb.connect()
for ext in ("httpfs", "spatial"):
    con.install_extension(ext)
    con.load_extension(ext)
con.execute("SET s3_region='us-west-2'")
con.execute(f"""
COPY (
  SELECT id, ST_X(geometry) AS lon, ST_Y(geometry) AS lat, names."primary" AS name,
         basic_category, taxonomy."primary" AS category, taxonomy.hierarchy AS hierarchy,
         taxonomy.alternates AS alt_categories, confidence,
         addresses[1].country AS country,
         list_transform(sources, lambda s: s.dataset) AS datasets
  FROM read_parquet('{SRC}', hive_partitioning=1)
  WHERE bbox.xmin BETWEEN 116.8 AND 126.7 AND bbox.ymin BETWEEN 4.5 AND 21.2
) TO '{out}' (FORMAT parquet)
""")
n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
print(f"Overture {RELEASE}: {n:,} places in the Philippine bounding box -> {out}")
