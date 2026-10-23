# Replicate the lottery-vs-wealth map in QGIS

A no-code path to the same map using the free desktop GIS, [QGIS](https://qgis.org).
Menu paths are for QGIS 3.34 LTR; wording differs slightly across versions.
All four datasets are free and need no login.

## 1. Get the data

1. **Wealth (Relative Wealth Index).**
   Open the HDX page <https://data.humdata.org/dataset/relative-wealth-index> and download `phl_relative_wealth_index.csv`.
   This is a ~2.4 km grid of relative-wealth scores (columns: `latitude, longitude, rwi, error`).
2. **Outlets (OpenStreetMap).**
   Open <https://overpass-turbo.eu/>, paste the query below, click **Run**, then **Export → download as GeoJSON** and save as `outlets.geojson`.
   This is a trimmed version of [`src/overpass_query.ql`](../src/overpass_query.ql), which the pipeline uses.
   ```
   [out:json][timeout:240];
   area["ISO3166-1"="PH"][admin_level=2]->.ph;
   (
     nwr["shop"="lottery"](area.ph);
     nwr["name"~"lotto|PCSO|Lottery",i]["shop"](area.ph);
   );
   out center tags;
   ```
3. **Population (WorldPop).**
   From <https://hub.worldpop.org/geodata/summary?id=49730> download the Philippines 2020 UN-adjusted 1 km population count GeoTIFF (`phl_ppp_2020_1km_Aggregated_UNadj.tif`).
4. **Boundaries (GADM).**
   From <https://gadm.org/download_country.html> download the Philippines GeoPackage (`gadm41_PHL.gpkg`).

## 1b. Or skip the downloads: connect live

You often do not need files on disk - QGIS reads several of these straight off web services.
Prefer the live path wherever it genuinely exists; use a download only where it does not.

- **Outlets, live from Overpass.**
  Install the **QuickOSM** plugin (Plugins -> Manage and Install Plugins), then QuickOSM -> Quick query: key `shop`, value `lottery`, extent = Philippines.
  It runs the Overpass query and loads the points with no export step.
- **Boundaries, live via WFS / ArcGIS REST.**
  Layer -> Add Layer -> Add WFS/OGC API Layer (or Add ArcGIS REST Server Layer) pointed at a live boundary service: the OCHA Common Operational Datasets ArcGIS FeatureServer for the Philippines, or a GeoJSON URL from the geoBoundaries API (`https://www.geoboundaries.org/api/current/gbOpen/PHL/ADM3/`).
  GADM itself has no live service.
- **Nighttime lights, live as tiles (a wealth/activity proxy that needs no download).**
  Layer -> Add Layer -> Add WMS/WMTS Layer pointed at NASA GIBS (VIIRS Day/Night Band), or use the Google Earth Engine QGIS plugin to pull the VIIRS collection.
- **Population, live via image service.**
  Add the WorldPop ArcGIS ImageServer (`https://worldpop.arcgis.com/arcgis/rest/services/WorldPop_Total_Population_1km/ImageServer`) as an ArcGIS REST / WCS layer, or the WorldPop layer from the Earth Engine plugin, instead of the GeoTIFF.
- **Already in a database?**
  If your data lives in PostGIS, Layer -> Add Layer -> Add PostGIS Layers and query the tables directly - no file handling at all.
- **What still needs a download.**
  The Meta RWI is a flat CSV and the PSA poverty tables are spreadsheets; there is no live tile/WFS endpoint for either.
  Fetch the file once - the RWI CSV loads fine from a remote URL in Add Delimited Text Layer.

## 2. Load the layers

1. Set the project CRS to EPSG:4326 (bottom-right of the QGIS window → search `4326`).
2. **Layer → Add Layer → Add Raster Layer** → add `phl_ppp_2020_1km_Aggregated_UNadj.tif`.
3. **Layer → Add Layer → Add Vector Layer** → add `gadm41_PHL.gpkg`; when prompted, add the `ADM_ADM_1` (regions) and `ADM_ADM_3` (cities/municipalities) sub-layers.
4. **Layer → Add Layer → Add Vector Layer** → add `outlets.geojson`.
5. **Layer → Add Layer → Add Delimited Text Layer** → add `phl_relative_wealth_index.csv`, set X field = `longitude`, Y field = `latitude`, geometry CRS = EPSG:4326.

## 3. Build the wealth base (choose one)

**Option A - grid/raster look (closest to the paper).**
Interpolate the RWI points to a smooth surface:
**Processing Toolbox → GDAL → Grid (IDW)** on the RWI layer, Z field = `rwi`, output cell size ~0.02°.
Then style the output raster: **Properties → Symbology → Singleband pseudocolor**, a diverging ramp, min/max set to the ~5th/95th percentile of `rwi` (about -1.2 and +1.5).

**Option B - points look (fastest, no interpolation).**
Style the RWI point layer itself: **Properties → Symbology → Graduated**, value = `rwi`, a diverging ramp, marker size ~4, opacity ~60%.

**Option C - wealth per neighbourhood (a true choropleth).**
Join wealth into city polygons:
**Processing → Vector general → Join attributes by location (summary)**, base = `ADM_ADM_3`, join = RWI points, summary statistic = **mean** of `rwi`.
Style `ADM_ADM_3`: **Symbology → Graduated** on `rwi_mean`, Natural Breaks (Jenks), diverging ramp.

## 4. Add the population control (so the comparison is fair)

To compare outlets *per person*, get population and outlet counts into the same areas.

1. **Population per area.**
   **Processing → Raster analysis → Zonal statistics**, input raster = WorldPop, zones = `ADM_ADM_3` (or your RWI grid), statistics = **Sum**.
   This adds a `pop_sum` column.
2. **Outlets per area.**
   **Processing → Vector general → Join attributes by location (summary)**, base = `ADM_ADM_3`, join = outlets, summary = **count** → adds an outlet-count column.
3. **Rate.**
   Open the ADM_3 attribute table → **Field Calculator** → new field
   `outlets_per_100k = "outlet_count" / "pop_sum" * 100000`.
   Sort by this column to read the wealth gradient directly: it is the same measure as the paper's decile table ([section 5.1](../README.md#51-outlets-per-person-by-wealth-decile)).

## 5. Add the outlets and finish

1. Style `outlets`: simple marker, dark-red fill (`#8C2E2E`), thin dark outline, size 2-3; move it to the top of the Layers panel.
2. **Metro Manila context:** in `ADM_ADM_1`, select *Metropolitan Manila*, right-click → **Export → Save Selected Features As**, then re-add it as an outline (no fill, dashed line).
3. **Compose:** **Project → New Print Layout**, add the map, a legend, a scale bar and a title, then **Layout → Export as Image / PDF**.

## Notes

- The paper's headline finding - outlets per capita *rising* with wealth nationally, but flat *within* Metro Manila - falls straight out of step 4 if you compute `outlets_per_100k` both nationally and for the ADM_3 areas inside NCR.
- Be honest about coverage: OSM outlet counts are a sample and skew urban/wealthy. State that on the map.
