# Lottery as a tax on the poor? A spatial study of lotto outlets in the Philippines

Earl Yu.
Open and published data only.

**Status.**
The research design was settled on 31 October 2026 and the data are collected (step 2 of 5).
This README sets out the question, the data and the planned analysis.
It holds no results yet: the models, findings and discussion come in steps 3 and 4.

| Step | Scope | Status |
|---|---|---|
| 1. Research design | Question, data sources, unit of analysis, models | Done (this README) |
| 2. Data collection | Fetch every source; place PCSO outlets; build one table per wealth tile and one per barangay; data-quality note | Done ([Data](#5-data)) |
| 3. Data analysis | Count and presence models, spatial checks, barangay check, road distance | Next |
| 4. Results and discussion | Findings, figures, maps, limitations | To do |
| 5. Clean-up | README as the finished paper; repo tidy | To do |

## Contents

1. [Background](#1-background)
2. [Research questions](#2-research-questions)
3. [Data sources](#3-data-sources)
4. [Research design](#4-research-design)
5. [Data](#5-data)
6. [How to reproduce](#6-how-to-reproduce)
7. [References](#references)

## 1. Background

This project started with Johnny Harris's video [*The US Lottery is a Lie*](https://www.youtube.com/watch?v=3Yn_3HqfV1w) (YouTube, 8 March 2023) [1].
It asks why US state governments run lotteries and where the money comes from, and makes the case that lottery revenue leans on lower-income players.
That is the familiar charge that the lottery is "a tax on the poor".
This study asks whether the same story can be seen on a map of the Philippines.

The Philippine lottery is a state enterprise, and a large one.
The Philippine Charity Sweepstakes Office (PCSO) runs Lotto, the Small Town Lottery (STL) and the sweepstakes.

| Measure | Value | Source |
|---|---|---|
| PCSO gaming revenue, 2023 | PHP 61.45 billion (about US$1.1 billion), up 7% on 2022 | Philstar [2] |
| PCSO gaming revenue, 2024 | PHP 62.35 billion, of which STL PHP 31.76 billion and Lotto with digit games PHP 29.72 billion | PCSO 2024 year-end report [3] |
| Price of a standard lotto play | PHP 20, rolled back from PHP 24 in 2020 | Philstar [4] |
| Lotto agents | 6,494 at the end of 2023 | PCSO Annual Report CY2023 [5] |
| Lotto outlets on PCSO's published map | 7,443, undated (pulled 30 October 2026) | PCSO outlet map [6] |
| For scale | more than 7-Eleven's stores (about 4,000) and Jollibee's branches (about 1,300) combined | Inquirer [7], Statista [8] |

The terminals and draw system are leased from private firms: in 2021 a joint venture of Pacific Online Systems, Philippine Gaming Management Corporation and International Lottery & Totalizator Systems won a five-year, PHP 5.8 billion nationwide lease [9].

What sharpens the question is where the money goes, because that is set by statute.
The PCSO's charter is Republic Act 1169 of 1954 [10].
Section 6, as amended by Batas Pambansa Blg. 42 in 1979, splits net receipts 55% to prizes, 30% to a charity fund for "health programs, medical assistance and services and/or charities of national character", and 15% to operations [11].
The Universal Health Care Act (Republic Act 11223, 2019) then directs 40% of that charity fund to PhilHealth [12].
The STL exists as a legal alternative to *jueteng*, the illegal numbers game penalised under Republic Act 9287 [13].
So a PHP 20 bet funds hospital bills by law, and it matters whose PHP 20 it is.

"A tax on the poor" bundles two claims.
The **access claim** is that outlets are concentrated in poorer neighbourhoods, which a map can test.
The **spending claim** is that poorer households spend a larger share of income on tickets, which only household budget data can test.
This study tests the access claim and says plainly what that does and does not tell us about the spending claim.

### What earlier studies found

Studies of where gambling and other retail outlets sit mostly count outlets per person in small areas and compare richer with poorer ones, using a count model with a population offset [14, 15, 16].
Gaming machines and betting shops tend to follow deprivation [14, 16].
Lottery retail is less clear: in New Jersey commercial land use was the strongest predictor and poverty turned negative [17], and in Massachusetts disadvantaged postcodes had no more agents or sales [18].
The stronger studies control for commerce, because outlets are shops and shops cluster in town centres.
No peer-reviewed lottery-outlet location study was found for the Philippines or another Asian middle-income country.

## 2. Research questions

1. **RQ1 Supply per person.** After accounting for population, are PCSO lotto outlets more or less common per person in poorer neighbourhoods than in richer ones?
   The access version of "a tax on the poor" predicts more outlets per person where people are poorer.
2. **RQ2 Commerce.** Does any wealth gradient hold among places with the same amount of shopping?
   Without a shops measure the model asks whether poorer Filipinos live with more or fewer outlets around them; with it, whether lotto leans towards poorer or richer places among places with the same retail.
3. **RQ3 Within cities.** Does the gradient hold inside Metro Manila, Metro Cebu and Davao City, where rich and poor neighbourhoods sit side by side?
4. **RQ4 Distance.** How far do people in poorer and richer neighbourhoods live from their nearest outlet, by road?

The spending claim is out of scope; it needs household spending on lotto by income, which the open data do not hold.

## 3. Data sources

Every source is public and free to download.
The choices were made on a methodology review of 22 studies and the Philippine data landscape, and each pick below says why it won.

| Role | Source | Grain | Year | Licence | Why this one |
|---|---|---|---|---|---|
| Outcome: lotto outlets | PCSO "Traditional Lotto Outlets" map [6] | Outlet: address, PCSO area, GPS text | Undated; pulled 30 Oct 2026 | Public PCSO publication | PCSO's own list, so it is complete by construction; 7,443 outlets against 6,494 agents at the end of 2023 |
| Wealth | Meta / Data for Good Relative Wealth Index (RWI) [19] | About 2.4 km tile, with a per-tile error | 2021 file | CC BY-NC 4.0 | The only open wealth measure finer than a city, so it can see rich and poor parts of the same city |
| Population count | PSA Census of Population, by barangay (via OCHA on HDX) | Barangay | 2020 (2024 planned) | HDX, PSA source | Official counts at the smallest administrative unit |
| Population pattern | WorldPop R2025A, constrained, 100 m | Pixel | 2024 | CC BY 4.0 | Spreads each barangay's census count to where its people live inside it |
| Boundaries and codes | OCHA COD-AB Philippines v03, PSGC codes | Barangay to region | Valid from Feb 2025 | CC BY-IGO | Official NAMRIA and PSA boundaries; 42,048 barangays |
| Shops | OpenStreetMap (Geofabrik) and Overture Maps places [20] | Point | Oct 2026 | ODbL; CDLA Permissive 2.0 and per-source terms | General shop counts for the commerce control; their own lotto points are left out |
| Roads | OpenStreetMap highways | Segment | Oct 2026 | ODbL | Road length as an urbanity control, and the network for RQ4 |

What was considered and not used:

- **OpenStreetMap or Overture lotto points as the outcome.** OpenStreetMap holds 397 lotto outlets, about 6% of PCSO's agents, so it is a small sample rather than a census; PCSO's own map replaces it.
- **Other outlet sources (Street View audit, LottoMatik's agent locator, Google Places).** PCSO's map is enough; Google's terms also forbid storing its places.
- **An eFOI request for PCSO's outlet list.** The published map already gives the list with locations.
- **PSA city and municipal poverty estimates as the wealth measure.** Not fine enough: wealth varies a lot inside Philippine cities, and a city-level rate would hide that. They stay available as a between-city cross-check.
- **Community-Based Monitoring System barangay poverty.** The only official barangay poverty measure, but held by local governments and not public; usable to validate the RWI where a city shares it.
- **The Small Town Lottery.** PCSO does not publish STL booth locations, so the national model covers PCSO lotto agents only.

## 4. Research design

### 4.1 Unit of analysis

The layers come at different grains: outlets are points, wealth is a 2.4 km grid, population is counted by barangay.
The design picks one unit and moves every layer onto it, which is the change-of-support problem [21].

- **Main unit: the RWI tile** (40,824 tiles).
  Wealth stays at its native grain.
  Outlets are counted per tile.
  Each barangay's census count is spread over its WorldPop 100 m pixels and summed per tile, which is dasymetric mapping [22].
- **Check: the barangay** (42,048).
  Population stays native, and wealth is the population-weighted RWI of the tiles its people live in.
  In cities several barangays share one tile's wealth value (Metro Manila's 1,712 barangays fall in 117 tiles), so standard errors are clustered by tile.

### 4.2 Planned models (step 3)

- **Count model.** Negative binomial (NB2) with estimated dispersion, outlets per tile as the outcome, log population as the offset so the result reads as outlets per person, and province intercepts to absorb PCSO branch practice and regional differences.
  Wealth enters as the RWI per standard deviation, so the answer is a rate ratio.
- **With and without commerce.** Each model is reported without and with shops (OpenStreetMap plus Overture), with road length and urban share as further controls (RQ2).
  Commerce may be a mediator as much as a confounder, which is why both are shown.
- **Presence model.** Logistic regression on whether a tile has any outlet.
- **Spatial checks.** Moran's I on the residuals; a BYM2 spatial model [23] if they cluster.
- **Within cities.** The same models inside Metro Manila, Metro Cebu and Davao City (RQ3).
- **Barangay check.** The same models per barangay, with tile-clustered errors.
- **Distance (RQ4).** Road distance from where people live to the nearest outlet, by wealth group.
- **Sensitivities.** Dropping GPS points that disagree with their address, adding outlets placed only at a town centre, and carrying the RWI's per-tile error through.

### 4.3 What the design can and cannot say

- The unit is the neighbourhood, not the person, and outlet location is not where buyers live.
- The RWI is a modelled, relative score, not income or a poverty rate, and its per-tile error is large next to differences inside a city.
- Shop mapping in OpenStreetMap and Overture is better in richer, urban places, so the commerce control is itself uneven.
- Even a perfect outlet map says nothing about how much each household spends relative to income.

## 5. Data

Step 2 builds two analysis-ready tables, each row carrying PCSO outlets, people, wealth and its error, shop counts, road length, urban share, province, region and PCSO sales area.

- [`data/derived/tiles.csv`](data/derived/tiles.csv): one row per RWI tile (40,824), the main unit.
- [`data/derived/barangays.csv`](data/derived/barangays.csv): one row per barangay (42,048), the check.
- [`docs/data-quality.md`](docs/data-quality.md): how each source was parsed and joined, the column dictionary, and where the gaps sit.

The data-quality headline:

- 7,284 of PCSO's 7,443 outlets (97.9%) are placed in a barangay, 133 more only at a town centre, and 26 (0.3%) cannot be placed.
- 331 GPS points disagree with the town in their address; they are kept and flagged.
- 99.4% of people live in a tile with an RWI value, and 99.6% of barangays join the census.
- Population is the 2020 census for now: the 2024 barangay counts sit behind a bot check on psa.gov.ph, and the note names the files for a manual swap.
- BARMM is the weakest region (135 barangays without a census match, 15 outlets).

PCSO's outlet addresses can carry owners' names, so the outlet list itself is never committed; only counts per tile and per barangay are.

| Step | Script | Writes |
|---|---|---|
| Download every source | [`src/fetch_data.sh`](src/fetch_data.sh), [`src/fetch_overture.py`](src/fetch_overture.py) | `data/raw/` (gitignored) |
| Shop points and roads from OpenStreetMap | [`src/osm_extract.py`](src/osm_extract.py) | `data/work/` (gitignored) |
| Barangays, census join, population on 100 m pixels, shops and roads per barangay | [`src/barangays.py`](src/barangays.py) | `data/work/`, `data/derived/barangays_summary.json` |
| Parse PCSO GPS text, check it against the address, place outlets without coordinates | [`src/pcso.py`](src/pcso.py) | `data/work/` (outlet rows), `data/derived/pcso_geocoding.json` |
| Tile and barangay tables, quality tables | [`src/tables.py`](src/tables.py) | `data/derived/` |

## 6. How to reproduce

Needs Python 3.12, `curl`, about 1.2 GB of downloads and 5 GB of memory.
Nothing is installed globally.

```bash
git clone https://github.com/earlcyu-petcircle/ph-lottery-outlets.git
cd ph-lottery-outlets
./run_all.sh              # venv, pinned packages, downloads, then every table in data/derived/
./run_all.sh --refresh    # same, but pull fresh PCSO, OpenStreetMap and Overture snapshots
```

Set `PYTHON=/path/to/python3.12` if `python3.12` is not on your path.
A run reuses anything already in `data/raw/`, so on the same downloads it reproduces the committed tables byte for byte; the table build takes about 2 minutes.
A `--refresh` run picks up a newer PCSO map, OpenStreetMap and Overture, so expect the counts to move.

Code is MIT licensed (see [LICENSE](LICENSE)); the data keep their own licences, listed above.

## References

1. Harris, J. *The US Lottery is a Lie.* YouTube, 8 March 2023. <https://www.youtube.com/watch?v=3Yn_3HqfV1w>
2. Philstar. "PCSO earns P61.45 billion in 2023." 22 April 2024. <https://www.philstar.com/nation/2024/04/22/2349455/pcso-earns-p6145-billion-2023>
3. Philippine Charity Sweepstakes Office. *Accomplishment Report 2024, Year-end.* 26 February 2025. <https://pcso-gov.ph/pcsofiles/transparency/12/Accomplishment%20Report%202024%20Yearend%20(20250226).pdf>
4. Philstar. "PCSO rolls back lotto ticket price." 8 June 2020. <https://www.philstar.com/headlines/2020/06/08/2019414/headlines>
5. Philippine Charity Sweepstakes Office. *Annual Report CY2023*, table "Lotto Agents, CY 2023". Read through a search index; pcso.gov.ph refuses scripted downloads.
6. Philippine Charity Sweepstakes Office. "Lotto Outlets" map. <https://www.pcso.gov.ph/Maps/Outlets.aspx>
7. Inquirer. "7-Eleven operator celebrates 4,000-store milestone in PH." <https://business.inquirer.net/485115/7-eleven-operator-celebrates-4000-store-milestone-in-ph>
8. Statista. "Number of Jollibee stores." <https://www.statista.com/statistics/1479196/number-of-jolibee-stores/>
9. BusinessWorld. "Pacific Online, partners bag lease for PCSO lottery system." 7 September 2021. <https://bworldonline.com/corporate/2021/09/07/394630/pacific-online-partners-bag-lease-for-pcso-lottery-system/>
10. Republic Act No. 1169 (1954), the PCSO Charter. LawPhil. <https://lawphil.net/statutes/repacts/ra1954/ra_1169_1954.html>
11. Batas Pambansa Blg. 42 (1979), amending RA 1169. LawPhil. <https://lawphil.net/statutes/bataspam/bp1979/bp_42_1979.html>
12. Republic Act No. 11223 (2019), Universal Health Care Act, Section 37(c). LawPhil. <https://lawphil.net/statutes/repacts/ra2019/ra_11223_2019.html>
13. Republic Act No. 9287 (2004), increasing penalties for illegal numbers games. Supreme Court E-Library. <https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/2/1457>
14. Wheeler, B. W., Rigby, J. E. and Huriwai, T. *Health & Place* 12 (1), 86-96, 2006. <https://doi.org/10.1016/j.healthplace.2004.10.011>
15. Kephart, L., Rees, V. W., Giovenco, D. P. and Subramanian, S. V. *American Journal of Preventive Medicine* 69 (2), 107643, 2025. <https://doi.org/10.1016/j.amepre.2025.107643>
16. Raisamo, S., Toikka, A., Selin, J. and Heiskanen, M. *BMC Public Health* 19, 1198, 2019. <https://doi.org/10.1186/s12889-019-7535-1>
17. Wiggins, L., Nower, L., Mayers, R. S. and Peterson, N. A. *Journal of Community Psychology* 38 (4), 486-496, 2010. <https://doi.org/10.1002/jcop.20376>
18. Pugh, Shirk and Volberg. *Journal of Gambling Studies* 42 (2), 663-683, 2026. <https://doi.org/10.1007/s10899-026-10475-6>
19. Chi, G., Fang, H., Chatterjee, S. and Blumenstock, J. E. "Microestimates of wealth for all low- and middle-income countries." *PNAS* 119 (3), e2113658119, 2022. <https://doi.org/10.1073/pnas.2113658119>
20. Overture Maps Foundation. "Places guide." <https://docs.overturemaps.org/guides/places>
21. Gotway, C. A. and Young, L. J. "Combining incompatible spatial data." *Journal of the American Statistical Association* 97 (458), 632-648, 2002. <https://doi.org/10.1198/016214502760047140>
22. Mennis, J. "Generating surface models of population using dasymetric mapping." *The Professional Geographer* 55 (1), 31-42, 2003. <https://doi.org/10.1111/0033-0124.10042>
23. Riebler, A., Sørbye, S. H., Simpson, D. and Rue, H. "An intuitive Bayesian spatial model for disease mapping that accounts for scaling." *Statistical Methods in Medical Research*, 2016. <https://doi.org/10.1177/0962280216660421>

Data: PCSO's published outlet map; Meta / Data for Good Relative Wealth Index via the Humanitarian Data Exchange (CC BY-NC 4.0); WorldPop, University of Southampton (CC BY 4.0); PSA 2020 census counts via OCHA; OCHA COD-AB Philippines (CC BY-IGO); © OpenStreetMap contributors (ODbL); Overture Maps places (CDLA Permissive 2.0 and per-source terms).
