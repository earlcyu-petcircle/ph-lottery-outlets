# Replicate the lottery-vs-wealth map as a Python web map

The path the paper uses: [GeoPandas](https://geopandas.org) for handling geodata, [Folium](https://python-visualization.github.io/folium/) / Leaflet for the interactive map, [statsmodels](https://www.statsmodels.org) for the hypothesis test.
Runnable end to end. The full scripts are in [`src/`](../src/).

## 1. Environment

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Or run the whole pipeline with `./run_all.sh` from the repo root, which does this for you.

## 2. Fetch the four open layers

Run `bash src/fetch_data.sh` from the repo root (each source is a single `curl`; the Overpass call needs a `User-Agent` header or it returns HTTP 406).
It downloads into `data/raw/`:

| File | Source | What it is |
|---|---|---|
| `osm_lottery_ph.json` | OpenStreetMap / Overpass API | lottery outlet points |
| `phl_rwi.csv` | Meta RWI via HDX | ~2.4 km wealth grid |
| `phl_pop_1km.tif` | WorldPop | 1 km population count raster |
| `gadm41_PHL.gpkg` | GADM 4.1 | admin boundaries |

## 2b. Or connect live (little or nothing on disk)

You often do not need to download physical files - several layers can be queried live over the web.
Outlets come live from Overpass; boundaries live from the geoBoundaries API; population and nighttime lights (an alternative wealth proxy) live from Google Earth Engine or a REST/image service.
The Meta RWI and PSA poverty tables have no live map service, so fetch those flat files once - programmatically via the HDX API, so there is still no manual clicking.

```python
import requests, geopandas as gpd, pandas as pd

# Outlets - live from the Overpass API (no download)
q = ('[out:json][timeout:240];area["ISO3166-1"="PH"][admin_level=2]->.ph;'
     '(nwr["shop"="lottery"](area.ph););out center tags;')
outlets = requests.post("https://overpass-api.de/api/interpreter",
                        data={"data": q},
                        headers={"User-Agent": "lottery-map/1.0"}).json()

# Boundaries - live from the geoBoundaries API (returns a GeoJSON URL to stream)
meta = requests.get("https://www.geoboundaries.org/api/current/gbOpen/PHL/ADM3/").json()
adm3 = gpd.read_file(meta["gjDownloadURL"])            # streamed, not saved

# Population & nighttime lights - live from Google Earth Engine (compute in the cloud)
import ee; ee.Initialize()
pop = ee.ImageCollection("WorldPop/GP/100m/pop").filter(ee.Filter.eq("year", 2020))
ntl = ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")   # wealth-activity proxy
#   ...reduceRegions() onto your grid, server-side; nothing downloaded.
#   WorldPop also has a plain REST API: https://www.worldpop.org/rest/data (1000 calls/day, no key)

# Meta RWI - NO live service; fetch the CSV programmatically via the HDX API
pkg = requests.get("https://data.humdata.org/api/3/action/package_show",
                   params={"id": "relative-wealth-index"}).json()
url = next(r["url"] for r in pkg["result"]["resources"] if "phl" in r["name"].lower())
rwi = pd.read_csv(url)                                 # streamed straight from the URL
```

Honest split: OSM outlets, boundaries and nighttime lights are genuinely "connect, don't download"; WorldPop is partly so (REST API / ImageServer / Earth Engine / stream the cloud-optimised GeoTIFF via rasterio `/vsicurl/`); the Meta RWI and PSA tables are flat files you fetch programmatically but cannot stream as a live map service.

## 3. Put everything on one grid (`analysis.py`)

The trick that avoids fiddly spatial joins: convert every feature to its **Web-Mercator tile at zoom 14** (~2.4 km, the RWI's native grid), then group by tile.

```python
import numpy as np
def lonlat_to_tile(lon, lat, z=14):
    n = 2**z
    x = np.floor((lon + 180)/360 * n).astype(int)
    y = np.floor((1 - np.arcsinh(np.tan(np.radians(lat)))/np.pi)/2 * n).astype(int)
    return x, y
```

- **RWI** → one row per tile with a wealth value.
- **Population** → assign each populated 1 km pixel centre to its tile, sum → population per tile.
- **Outlets** → assign each outlet to its tile, count → outlets per tile.

Merge on `(tile_x, tile_y)` and you have one row per ~2.4 km cell: `{rwi, pop, n_outlets}`.
No `sjoin`, no CRS headaches - just integer tile keys.

## 4. Test the hypothesis (`analysis.py`)

Two complementary tests:

1. **Per-capita by wealth decile.**
   Cut cells into ten bins of *equal population* (not equal cell count), then compute `outlets / pop * 100000` per bin.
   ```python
   # population-weighted deciles, then outlets per 100k
   order = np.argsort(cells.rwi.values); w = cells.pop.values[order]
   cw = np.cumsum(w)/w.sum()
   edges = np.searchsorted(cw, np.linspace(0,1,11)[1:-1])
   ```
2. **Negative-binomial count model** with a log-population offset (so the response is a per-capita rate):
   ```python
   import statsmodels.api as sm, statsmodels.formula.api as smf
   reg["rwi_z"] = (reg.rwi - reg.rwi.mean())/reg.rwi.std()
   m = smf.glm("n_outlets ~ rwi_z", data=reg,
               family=sm.families.NegativeBinomial(alpha=1.0),
               offset=np.log(reg["pop"])).fit()
   # exp(coef) = incidence-rate ratio per +1 SD of wealth
   ```
   A *negative, significant* wealth coefficient would support "tax on the poor". In this data it comes out *positive* (IRR about 2.2) - mapped outlets track wealth, mostly via urbanicity and mapping coverage.

## 5. Render the interactive map (`map.py`)

Paint the RWI onto a coloured PNG and drop it on Leaflet as an `ImageOverlay`; add outlets as `CircleMarker`s.

```python
import folium, pandas as pd
odf = pd.read_csv("data/derived/outlets_clean.csv")
m = folium.Map(location=[12.6, 122.5], zoom_start=6, tiles="OpenStreetMap")
folium.raster_layers.ImageOverlay(          # wealth base, built from the RWI grid
    image="rwi.png",
    bounds=[[4.55, 116.85], [21.15, 126.65]],
    opacity=0.85, name="Neighbourhood wealth").add_to(m)
for _, r in odf.iterrows():                 # outlets on top
    folium.CircleMarker([r.lat, r.lon], radius=3, color="#3B0D0D",
        fill=True, fill_color="#8C2E2E", fill_opacity=0.9,
        popup=str(r["name"])).add_to(m)
folium.LayerControl().add_to(m)
m.save("lottery_map.html")
```

Open `lottery_map.html` in any browser - pan, zoom, toggle layers, click a point for its name.
See `../src/map.py` for the full version with the legend, title card and Metro Manila outline.

## 6. Robustness and variations

- **Within-Metro-Manila check** (`robustness.py`): clip cells to the NCR polygon from GADM and re-run the decile + model tests. The wealth gradient flattens - evidence the national gradient is urbanicity/coverage, not a within-place effect.
- **Base-map note:** CartoDB/Stamen tiles now need API keys; `tiles="OpenStreetMap"` is keyless and reliable.
- **Slicker maps:** swap Folium for `kepler.gl` or `pydeck` for GPU/3-D rendering, or add a municipality choropleth with `folium.Choropleth` over the GADM ADM_3 layer joined to mean RWI.

## Tips / gotchas

- Overpass returns **HTTP 406** without a `User-Agent` header - always send one.
- Use **Python 3.12** (or 3.11); the heavy geo wheels (`rasterio`, `geopandas`) may lag on the newest Python.
- RWI is a *relative* 2021 proxy with per-cell error - treat small differences cautiously.
- OSM outlet coverage is uneven and skews urban/wealthy; report that alongside any result.
