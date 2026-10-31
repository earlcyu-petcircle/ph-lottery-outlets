# Data collection and quality (step 2)

This note covers step 2 of the study: collecting the data and building the two analysis-ready tables.
It reports how complete each layer is and where the gaps sit, so steps 3 and 4 know what they are standing on.
It holds no models and no findings.

Every number here is rebuilt by `./run_all.sh` from the downloads in `data/raw/`; the machine-readable versions are in [`data/derived/`](../data/derived/) (`data_quality.json`, `quality_by_area.csv`, `quality_by_region.csv`, `pcso_geocoding.json`, `barangays_summary.json`).
Snapshots in this build: PCSO outlet map pulled 30 October 2026, OpenStreetMap extract of 29 October 2026, Overture release 2026-10-21.0.

## The short version

- **The outcome is close to complete.** PCSO's published outlet map lists 7,443 traditional lotto outlets, and 7,284 (97.9%) are placed in a barangay; another 133 are placed at a town's centre, and only 26 (0.3%) cannot be placed at all.
- **The map holds more outlets than PCSO's last annual count.** 7,443 against 6,494 lotto agents at the end of 2023 (115%), and more in every PCSO area, so the map is a later snapshot (probably 2024-2026) rather than a partial one.
- **Coordinates are mostly usable as published.** 7,061 outlets (94.9%) have GPS text that parses to a point in the Philippines, 277 of them only after repairing an odd separator or a lost decimal point.
- **About 1 in 22 GPS points disagrees with its address.** 331 of 7,042 GPS-placed outlets fall outside the town their address names (221 within 10 km of it, 91 further) or name no town that could be read; they are kept and flagged, not moved.
- **Wealth and people cover almost everyone.** 99.4% of people live in a tile with a Relative Wealth Index (RWI) value, and 99.6% of barangays join to the 2020 census.
- **The weak spots are BARMM and the population vintage.** BARMM has 135 barangays without a census match and 41 without RWI, and the population is the 2020 census, because the 2024 barangay counts are behind a bot check on psa.gov.ph.

## What was collected

| Layer | Source | Grain | Year | Licence | Rows |
|---|---|---|---|---|---:|
| Lotto outlets (outcome) | PCSO "Traditional Lotto Outlets" map, KML export of its Google My Maps layer | Outlet, address and free-text GPS | Undated; pulled 30 Oct 2026 | Public PCSO publication, no licence stated; only aggregates committed | 7,443 |
| Wealth | Meta / Data for Good Relative Wealth Index (HDX) | 2.4 km tile (zoom-14 quadkey), with a per-tile error | 2021 file | CC BY-NC 4.0 | 40,824 tiles |
| Population pattern | WorldPop R2025A, constrained, 100 m | Pixel | 2024 | CC BY 4.0 | 9.63M populated pixels |
| Population count | PSA 2020 Census of Population and Housing by barangay, 10-digit PSGC, with urban/rural flag (OCHA on HDX) | Barangay | 2020 | HDX, PSA source | 41,984 |
| Boundaries and codes | OCHA COD-AB Philippines v03 (NAMRIA and PSA), PSGC-based pcodes | Region to barangay | Valid from Feb 2025; files 28 May 2026 | CC BY-IGO | 42,048 barangays |
| Shops and food | OpenStreetMap, Geofabrik Philippines extract | Point | 29 Oct 2026 | ODbL | 107,323 shops, 54,960 food, drink, pharmacy and market points |
| Shops and food | Overture Maps places (`shopping` and `food_and_drink`) | Point | Release 2026-10-21.0 | CDLA Permissive 2.0 and per-source terms | 197,390 shops, 211,393 food and drink |
| Roads | OpenStreetMap highways (motorway to service, residential and unclassified roads; no paths or tracks) | Segment | 29 Oct 2026 | ODbL | 365,254 km |

Both commerce sources leave out their own lotto points (OSM `shop=lottery` or a lotto, PCSO, STL or lottery name: 605; Overture `lottery_vendor` or such a name: 219), because commerce is a control and must not contain the outcome.

## The PCSO outlet map

### Parsing the GPS text

The KML has no geometry: each outlet has its address, its PCSO area and a `GPSCoordinates` text field typed by hand.

| GPS text | Outlets | Handling |
|---|---:|---|
| Decimal pair, `lat, lon` (any of `, ; /` or a space between) | 5,656 | Read as is; reversed pairs swapped, wrong signs dropped |
| Degrees, minutes, seconds with the degree sign lost (`8 5'50.21"N 12329'14.42"E`) | 1,128 | Degree and minute digits split by position; minutes or seconds of 60 or more rejected |
| Decimal pair with an odd separator or a lost decimal point (`14.5-121.0`, `14.5 : 121.0`, `14.5, 1210123`) | 277 | Repaired; 92% then agree with their address, against 96% of clean decimal pairs |
| Blank | 298 | Placed from the address |
| Malformed (a single number, three numbers, mixed formats) | 72 | Placed from the address |
| Outside 4.2-21.5 N, 116.0-127.5 E | 11 | Placed from the address |
| Unreadable degree-minute-second | 1 | Placed from the address |

### Placing each outlet

| Status | Outlets | Meaning | In the tables |
|---|---:|---|---|
| `gps_consistent` | 6,711 | Point in (or within 1 km of) a barangay of the town its address names | `outlets` |
| `gps_other_town` | 221 | Address names another town, and the point is within 10 km of it (median 1.2 km: mostly town borders) | `outlets`, flagged |
| `gps_far` | 91 | Every town the address names is more than 10 km away (median 19 km) | `outlets`, flagged |
| `gps_town_unnamed` | 19 | No town in the outlet's PCSO area could be read from the address | `outlets`, flagged |
| `address_barangay` | 242 | No usable point; barangay and town read from the address, placed at the barangay's population-weighted centre | `outlets` |
| `address_town` | 133 | Only the town could be read; placed at the town's population-weighted centre | Tiles only, `outlets_address_town`, kept out of `outlets` |
| `unplaced_town_ambiguous` | 21 | Several towns fit and the province did not settle it | Not counted |
| `unplaced` | 5 | No town could be read | Not counted |

Address matching runs offline against COD-AB names (town, then barangay inside it, inside the outlet's PCSO area), because the addresses carry some owners' names and are not sent to any geocoding service.
Each status has its own column in both tables, so step 3 can drop the flagged points or add the town-only ones as sensitivity checks.
12 address strings appear twice; they are kept, since one shop can hold more than one terminal.

### Coverage against PCSO's CY2023 annual report

| PCSO area | Map outlets | Placed in a barangay | CY2023 agents | Map / CY2023 | Map outlets per 100k | CY2023 agents per 100k |
|---|---:|---:|---:|---:|---:|---:|
| National Capital Region | 1,998 | 1,976 | 1,850 | 1.08 | 14.8 | 13.7 |
| Northern and Central Luzon | 1,282 | 1,265 | 1,111 | 1.15 | 5.5 | 4.8 |
| Southern Luzon and Bicol Region | 1,933 | 1,879 | 1,695 | 1.14 | 7.6 | 6.6 |
| Visayas | 1,385 | 1,340 | 1,124 | 1.23 | 6.7 | 5.5 |
| Mindanao | 845 | 824 | 636 | 1.33 | 3.2 | 2.4 |
| Total | 7,443 | 7,284 | 6,416 (printed 6,494) | 1.16 | 6.8 | 5.9 |

The CY2023 figures are lotto agents at 31 December 2023 from PCSO's Annual Report CY2023 (table "Lotto Agents, CY 2023").
pcso.gov.ph refuses scripted downloads (HTTP 403), so they were read through a search index on 30 October 2026 and have not been checked against the PDF; the five area rows sum to 6,416 against a printed total of 6,494.
Per-100k rates use the 2020 census.
The map exceeds the 2023 count in every area, by most in Mindanao and least in NCR; it carries no date, so it may also still list some closed outlets.

### Where outlets are still unplaced or placed only roughly

- **Unplaced (26):** Southern Luzon and Bicol 12, Visayas 7, Mindanao 3, Northern and Central Luzon 2, NCR 2.
- **Town centre only (133):** Bicol 27, Eastern Visayas 20, NCR 20, Western Visayas 14, Calabarzon 13, Caraga 9, the rest 6 or fewer each.
- **Barangay centre from the address (242):** Bicol 52, Cagayan Valley 40, Calabarzon 31, NCR 24, Eastern Visayas 23, the rest under 15 each.
- Western Visayas was the board's big gap (250 outlets without coordinates); 231 of its points were rescued by the separator repair, so it now looks like other regions.

## Missingness by region

| Region | Outlets located | GPS flagged | From address (barangay / town) | Outlets per 100k | Barangays without census match | Barangays without RWI | People in RWI tiles | Shops per 1,000 people |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| I Ilocos | 218 | 1.9% | 3 / 0 | 4.1 | 0 | 1 | 99.7% | 2.51 |
| II Cagayan Valley | 194 | 3.4% | 40 / 6 | 5.3 | 0 | 6 | 98.8% | 1.36 |
| III Central Luzon | 786 | 9.5% | 14 / 5 | 6.3 | 3 | 2 | 99.7% | 3.14 |
| IV-A Calabarzon | 1,422 | 6.4% | 31 / 13 | 8.8 | 1 | 4 | 99.9% | 3.50 |
| V Bicol | 284 | 5.9% | 52 / 27 | 4.7 | 0 | 1 | 99.6% | 1.15 |
| VI Western Visayas | 352 | 5.5% | 8 / 14 | 4.4 | 11 | 2 | 99.8% | 2.19 |
| VII Central Visayas | 485 | 2.1% | 6 / 4 | 6.0 | 0 | 6 | 99.7% | 2.76 |
| VIII Eastern Visayas | 539 | 1.0% | 23 / 20 | 11.8 | 3 | 24 | 98.9% | 1.69 |
| IX Zamboanga Peninsula | 232 | 5.3% | 2 / 3 | 6.0 | 5 | 1 | 99.4% | 1.23 |
| X Northern Mindanao | 171 | 4.8% | 2 / 1 | 3.4 | 2 | 6 | 99.2% | 1.91 |
| XI Davao | 232 | 1.4% | 8 / 3 | 4.4 | 1 | 1 | 98.9% | 3.18 |
| XII Soccsksargen | 101 | 1.0% | 2 / 2 | 2.3 | 3 | 2 | 99.4% | 1.19 |
| NCR | 2,000 | 4.2% | 24 / 20 | 14.8 | 3 | 0 | 100.0% | 6.28 |
| CAR | 88 | 0.0% | 3 / 4 | 4.9 | 0 | 1 | 98.8% | 2.89 |
| XIII Caraga | 90 | 8.6% | 11 / 9 | 3.2 | 0 | 1 | 98.3% | 1.41 |
| Mimaropa | 208 | 2.1% | 13 / 2 | 6.4 | 10 | 13 | 98.2% | 1.48 |
| BARMM | 15 | 0.0% | 0 / 0 | 0.3 | 135 | 41 | 96.5% | 0.21 |

"Outlets located" counts outlets placed in the region by GPS or address, including town-centre ones; "GPS flagged" is the share of GPS-placed outlets with a `gps_other_town`, `gps_far` or `gps_town_unnamed` status.
Reading it:

- **BARMM is the one region to treat with care.** 15 outlets for 4.9M people may be real (PCSO's Mindanao figure does not split BARMM out), and its census join and RWI coverage are the weakest.
  Of its 135 unmatched barangays, 63 are in the Special Geographic Area (Cotabato barangays that joined BARMM and were regrouped into new municipalities) and 70 in Maguindanao del Sur and del Norte, where towns were split or renamed after 2020.
- **Eastern Visayas has an unusually high outlet rate (11.8 per 100k)**, second only to NCR, and 24 barangays without RWI; worth a look in step 3 before reading it as a finding.
- **Shop mapping is uneven:** 6.3 shops per 1,000 people in NCR against 0.2 in BARMM and about 1.2 in Bicol and Soccsksargen, which is the reason the count model is run with and without the shops measure.
- **Central Luzon and Caraga have the most flagged GPS points (9.5% and 8.6%)**, mostly points just across a town border.

## The other layers

- **Census join:** 38,501 barangays match the 2020 census on PSGC code, 3,370 more on town and barangay name (codes that changed after 2020), and 177 do not match (135 in BARMM); those take their WorldPop 2024 count instead (585,000 people, 0.5% of the total) and have no urban flag.
- **Population total:** 109.14M, against 108.82M in the 2020 census table; the difference is the WorldPop fill-in for the 177 unmatched barangays.
- **Dasymetric step:** each barangay's census count is spread over its WorldPop 2024 100 m pixels in proportion to WorldPop's own estimate, then summed per tile; 99.7% of WorldPop's people fall inside a COD-AB barangay, and the 77 barangays with no populated pixel keep their count at their interior point.
- **RWI:** every tile in the table has an RWI value and error by construction; 99.4% of people live in such a tile, and 13 placed outlets fall outside one.
  Per-tile error runs from 0.40 to 0.88 (mean 0.53), against an RWI spread of -1.76 to 2.29.
  For barangays, RWI and its error are population-weighted over the tiles their people live in; 48 barangays with no populated pixel in an RWI tile take the tile under their interior point, and 112 (72,000 people, no outlets) have none.
- **Shops:** OSM and Overture agree on where shops are (correlation of log counts per tile 0.81), but Overture lists nearly twice as many; 25% of tiles have at least one shop.
- **Urban share:** the share of a tile's people living in barangays the 2020 census calls urban; it is missing for 140 tiles, 87 with nobody living in them and 53 whose people all live in unmatched barangays.

## The 2024 census: manual swap

The design calls for 2024 census (POPCEN) counts, official under Proclamation No. 973 of 11 July 2025 (112,729,484 people at 1 July 2024).
They are published only on psa.gov.ph, which serves scripts a Cloudflare bot check, so this build uses the 2020 counts.
The files to fetch by hand, as listed by a search index (the page itself could not be opened from a script):

- Page: [2024 Census of Population (POPCEN) Population Counts Declared Official by the President](https://psa.gov.ph/content/2024-census-population-popcen-population-counts-declared-official-president).
- Files: one Excel workbook per region, each titled "Table C - Population by Barangay" (the search index lists NCR, CAR, Regions I-III, Calabarzon, Mimaropa, Region V, NIR, Caraga and BARMM among them).
- Place them in `data/manual/popcen2024/` (gitignored); a loader for them is a follow-up, since their layout has not been seen.

The 2024 tables follow the 2024 PSGC, which includes the Negros Island Region (NIR); COD-AB v03 predates NIR, so the join will need a region crosswalk for Negros Occidental, Negros Oriental and Siquijor.

## The tables

### `data/derived/tiles.csv` (40,824 rows, one per RWI tile)

| Column | Meaning |
|---|---|
| `quadkey` | Zoom-14 Bing quadkey, the RWI tile id |
| `lon`, `lat` | The RWI file's point for the tile |
| `tile_km2` | Ground area of the tile |
| `rwi`, `rwi_error` | Relative Wealth Index and its error |
| `outlets` | PCSO outlets placed in a barangay (GPS or address barangay): the main count |
| `outlets_gps`, `outlets_gps_consistent`, `outlets_gps_other_town`, `outlets_gps_far`, `outlets_gps_town_unnamed`, `outlets_address_barangay` | The same, split by placement status |
| `outlets_address_town` | Outlets placed only at a town's centre (not in `outlets`) |
| `pop` | People: 2020 census counts spread over WorldPop 2024 100 m pixels |
| `worldpop_2024` | WorldPop's own count, for comparison |
| `n_barangays` | Barangays with people in the tile |
| `urban_share` | Share of the tile's people in census-urban barangays |
| `shops`, `shops_osm`, `shops_overture` | Shop points (OSM plus Overture, then each) |
| `food_osm`, `food_overture` | Food and drink points (OSM also counts pharmacies and markets) |
| `road_km` | OSM road length |
| `province_pcode`, `province`, `region_pcode`, `region`, `pcso_area`, `metro` | From the barangay holding most of the tile's people; `metro` is Metro Manila, Metro Cebu (its 13 LGUs), Davao City or "Rest of the country" |

### `data/derived/barangays.csv` (42,048 rows, one per COD-AB barangay)

| Column | Meaning |
|---|---|
| `adm4_pcode` ... `region` | COD-AB names and PSGC-based pcodes, town to region |
| `pcso_area`, `metro` | As for tiles |
| `area_km2` | COD-AB area |
| `pop`, `pop_source` | 2020 census count, or WorldPop 2024 where there is no census match |
| `worldpop_2024` | WorldPop's own count |
| `urban` | 1 if the 2020 census calls the barangay urban |
| `rwi`, `rwi_error`, `rwi_source` | Population-weighted RWI and error; `pixels`, `centre_tile` or `none` |
| `main_tile`, `n_tiles` | Quadkey of the tile holding most of its people (the cluster for tile-clustered errors), and how many tiles its people span |
| `outlets` ... `outlets_address_barangay` | As for tiles (town-centre outlets cannot be put in a barangay) |
| `shops` ... `road_km` | As for tiles |

## Limitations

- The PCSO map is undated and may list closed outlets; the comparison with CY2023 rests on figures not checked against the PDF.
- GPS points are as PCSO published them; flagged points are kept where they are, and address-placed outlets sit at a population-weighted centre, not their shop.
- Address matching is by name; a town that shares a name with a street can make a wrong point look consistent.
- Population is the 2020 census on a 2024 WorldPop pattern; the RWI is a 2021 estimate built partly from phone and connectivity data, and its per-tile error is large next to differences inside a city.
- OSM and Overture shop listings are themselves better in richer and more urban places.
