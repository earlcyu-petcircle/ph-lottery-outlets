# Do poorer Filipinos have easier access to PCSO lottery outlets than richer Filipinos?

By: Earl Christian Yu
<br/>Published on: 04 November 2026
<br/>Last edited: 04 November 2026

*This is the full paper behind the one-page story site at <https://earlcyu-petcircle.github.io/ph-lottery-outlets/>, which carries the same results with an interactive map.*

## Summary

< to be finalized >

![Wealth and outlet density together, Philippines: most of the country is poorer tiles with no outlet, and the tiles that are both richer and above the national outlet rate cluster in Metro Manila and the larger cities](../results/figures/map_national_bivariate.png)

## Contents

1. [Background](#1-background)
2. [Research questions](#2-research-questions)
3. [Data sources](#3-data-sources)
4. [Research design](#4-research-design)
5. [Data](#5-data)
6. [Results](#6-results)
7. [Discussion](#7-discussion)
8. [Limitations](#8-limitations)
9. [Conclusion and future work](#9-conclusion-and-future-work)
10. [How to reproduce](#10-how-to-reproduce)
11. [References](#references)
12. [Appendix A. Code and pipeline](#appendix-a-code-and-pipeline)
13. [Appendix B. Every figure and table](#appendix-b-every-figure-and-table)
14. [Appendix C. Project history](#appendix-c-project-history)

## 1. Background

### 1.1 Inspiration

A few years ago, I came across [this YouTube video by Johnny Harris](https://www.youtube.com/watch?v=3Yn_3HqfV1w) [[1](#ref-1)] that shows why the US lottery is **"a tax on the poor"**. It is a way to tax people disguised as a fun game: you pay a small amount for a lotto ticket and get a chance to win a life-changing amount of money. In the US, poorer households spend as much as 33 times more on lotto tickets than richer households [[2](#ref-2)]. No wonder the lottery became known as a tax on the poor.

That got me thinking. **Is the Philippine lottery also a tax on poor Filipinos?** There are two ways to test this: **access and spend**. 
- **Access:** Are there more lotto outlets in poorer neighborhoods than richer ones?
- **Spend:** Do poorer households spend more on lotto tickets than richer households? 

The first question can be answered via spatial analysis and is the main scope of this paper. The second question, while also a crucial dimension, will not be part be part of this paper.

### 1.2 Philippine lottery

The Philippine Charity Sweepstakes Office (PCSO) is a government-owned and controlled corporation that runs the country's national and local lotteries. As of 2024, it recorded a revenue of PHP 62.35 billion [[3](#ref-3)]. It operates 7,443 outlets nationwide [[4](#ref-4)] - more than the number of 7-11 convenience stores (~4,000) [[5](#ref-5)] and Jollibee branches (~1,300) [[6](#ref-6)] in the country.

![PCSO gaming revenue in 2024 by game: Small Town Lottery PHP 31.76 billion, Lotto with digit games PHP 29.72 billion and other games PHP 0.87 billion, of PHP 62.35 billion](../results/figures/pcso_gaming_revenue_2024.png)

How the PCSO spends its money is dictated by law: 55% to prizes, 30% to a charity fund for "health programs, medical assistance and services, and/or charities of national character", and 15% to operations [[7](#ref-7)]. Moreover, the Universal Health Care Act (RA 11223) directs 40% of that charity fund to PhilHealth [[8](#ref-8)].

![Where PCSO's net receipts go by law: 55% to prizes, 30% to the charity fund and 15% to operations](../results/figures/pcso_net_receipts_split.png)

## 2. Research questions

1. **Outlets per person.** Are PCSO lotto outlets more or less common per person in poorer neighborhoods than in richer ones? Does the answer change once we account for province, how urban a place is, how many shops it has, and its road length?
3. **Within cities.** Does the rich-poor pattern persist in Metro Manila, Metro Cebu, and Metro Davao, where the poor and rich sit close together?
4. **Road distance.** How far do people in poor and rich neighbourhoods live from the nearest lotto outlet?

## 3. Data sources

### 3.1 Selected data sources

Every source is public and free to download. Why each data source was chosen is indicated in the table below:

| Data | Source | Grain | Year | Licence | Why this was chosen |
|---|---|---|---|---|---|
| Lotto outlets | PCSO "Traditional Lotto Outlets" map [[4](#ref-4)] | Point | Undated; pulled 2 Nov 2026 | Public PCSO publication | PCSO's own list, so it is complete by construction; 7,443 outlets against 6,494 agents at the end of 2023 |
| Wealth | Meta / Data for Good Relative Wealth Index (RWI) [[9](#ref-9)] | About 2.4 km tile, with a per-tile error | 2021 file | CC BY-NC 4.0 | The only open wealth measure finer than a city, so it can see rich and poor parts of the same city |
| Population count | PSA 2024 Census of Population, by barangay (downloaded by hand) | Barangay | 1 Jul 2024 | PSA publication | Official counts at the smallest administrative unit |
| Urban share | JRC GHSL Degree of Urbanisation | 1 km cell | 2025 epoch | CC BY 4.0 | A standard international urban definition, since the 2024 census carries no urban flag |
| Population pattern | WorldPop R2025A, constrained, 100 m | Pixel | 2024 | CC BY 4.0 | Spreads each barangay's census count to where its people live inside it |
| Boundaries and codes | OCHA COD-AB Philippines v03, PSGC codes | Barangay to region | Valid from Feb 2025 | CC BY-IGO | Official NAMRIA and PSA boundaries; 42,048 barangays |
| Shops | OpenStreetMap (Geofabrik) and Overture Maps places [[10](#ref-10)] | Point | Oct-Nov 2026 | ODbL; CDLA Permissive 2.0 and per-source terms | General shop counts for the commerce control; their own lotto points are left out |
| Roads | OpenStreetMap highways | Segment | Nov 2026 | ODbL | Road length as an urbanity control, and the network for RQ4 |

### 3.2 Unselected data sources

| Data | Source | Reason |
|---|---|---|
| Lotto outlets | OpenStreetMap | It only contains 397 lotto outlets, ~6% of PCSO's outlets. |
| Wealth | PSA city and municipal poverty estimates | Not granular enough; wealth varies a lot within cities, so a city-level measure would hide that nuance. |

## 4. Research design

| # | Research question | Data used | Methods used |
|---|---|---|---|
| RQ1 | Are PCSO lotto outlets more or less common per person in poorer neighborhoods than in richer ones?<br/>Does the answer change once we account for province, how urban a place is, how many shops it has, and its road length? | - PCSO lotto outlets counted per tile<br/> - Meta Relative Wealth Index, per 2.4 km tile<br/> - 2024 census population, spread onto tiles with WorldPop<br/> - GHSL urban share<br/> - Shop counts: OpenStreetMap and Overture<br/> - Road distance: OpenStreetMap | - **Descriptive statistics:** count of outlets per 100,000 people by population-weighted wealth quintile<br/> - **Regression model:** negative binomial regression and logistic regression<br/> |
| RQ2 | Does the rich-poor pattern persist in Metro Manila, Metro Cebu, and Metro Davao, where the poor and rich sit close together? | - RQ1 data cut to each city<br/> - official city boundaries | - same as RQ1 |
| RQ3 | How far do people in poor and rich neighbourhoods live from the nearest lotto outlet? | - OpenStreetMap road network<br/> - population on WorldPop 100m pixels<br/> - outlet points<br/> - wealth quintiles | - **Road distance:** Dijkstra's algorithm<br/> - **Descriptive statistics:** median road distance and share within 2km by wealth quintile, with straight-line distance alongside. |

### 4.1 Unit of analysis

The data come at various grains: lotto outlets are points, the wealth index is a 2.4km grid, and population is at a barangay-level. The design picks one unit and moves every layer onto it, which is the change-of-support problem [[11](#ref-11)].

| Unit chosen | Purpose | Notes |
|---|---|---|
| RWI tile (40,824 tiles, 40,737 with people) | For nationwide analysis | Wealth stays on its native grain.<br/> Outlets are counted per tile.<br/> Each barangay's census count is spread over its WorldPop 100 m pixels and summed per tile, which is dasymetric mapping [[12](#ref-12)]. |
| Barangay | For metro city comparisons | Population stays native, and wealth is the population-weighted RWI of the tiles its people live in.<br/> In cities, several barangays share one tile's wealth value (Metro Manila's 1,711 barangays in the models have most of their people in 113 tiles), so standard errors are clustered by tile.

### 4.2 Descriptive statistics

A simple way to answer the core research question is calculate the number of lotto outlets per 100,000 people and compare that number among various wealth quintiles. The wealth quintiles are formed by categorizing the 40,824 RWI tiles into five groups, each with roughly the same population. Since poor areas are sparse and rural, the lowest quintile will likely consist of a lot of tiles while the top quintile will contain fewer tiles.

< insert image that illustrates the quintile process >

### 4.3 Negative binomial regression

A negative binomial regression model predicts the count of something and determines if a certain variable is a strong predictor of that count. This study applies the model to determine if wealth is a strong predictor of the count of lotto outlets per person in a given location. 

The model predicts the expected count through a log:

$$\log E[\text{outlets}_i] = \log(\text{pop}i) + \alpha{\text{province}} + \beta \cdot \frac{\text{RWI}_i}{0.49} + \gamma' x_i$$

- **The offset, log(population):** this term has its coefficient fixed at 1. It turns the model from “outlets” into “outlets per person”, so big tiles don’t win just by having more people.
- **The final answer is rate ratio:** how many times as many outlets per person a place one standard deviation richer has, with the other variables held constant. For example, if the final rate ratio is 2, that means that a place one standard deviation richer has 2x lotto outlets per person.
- **Adding controls:** Control variables can be included to prevent them from distorting the predictor's answer. For this study, the controls are urban share, province intercept, and count of shops. By including these variables, the model will only compare tiles that have the same control variables to ensure that the control variables are not the ones responsible for predicting the final count. 
- **Why negative binomial instead of Poisson:** Poisson assumes the variance equals the mean. Real counts are messier: lots of zeros, plus a few places with large clusters. Negative binomial adds a dispersion term, so the variance is μ + αμ². One way to picture it is that every place has its own hidden “appetite” for outlets beyond what the predictors explain. Poisson would ignore that extra spread and report confidence intervals that are too narrow.

### 4.4  Djikstra's algorithm

This algorithm is used to determine the shortest path using real roads to the nearest lotto outlet. People are placed on 100m population pixels. Each pixel and each outlet is snapped to the nearest road, then one search from all outlets at once gives every location its distance by road to the closest outlet.

### 4.5 Other models

- **Logistic regression:** This model predicts whether or not something is present. In this case, it can predict whether or not a tile contains a lotto outlet by calculating the probability that it contains one. Logistic regression was done to back up the results of the negative binomial regression model.
- **Spatial checks:** Moran's I on the residuals; where they cluster, a refit with Moran eigenvector spatial filters, a frequentist stand-in for a BYM2 spatial model [[13](#ref-13)].

### 4.6 What the research design can and cannot say

- The RWI is a modelled, relative score. It is not an income or a poverty rate, and its per-tile error is large next to differences inside a city.
- Shop mapping in OpenStreetMap and Overture is better in richer, more urban places, so the commerce control is itself uneven.
- Even a perfect outlet map says nothing about how much each household spends on lotto tickets. That entails a separate analysis.

## 5. Processed data

Two analysis-ready tables hold every input to the models, each row carrying PCSO outlets, people, wealth and its error, shop counts, road length, urban share, province, region and PCSO sales area.

| File name | Description |
|---|---|
| [`data/derived/tiles.csv`](../data/derived/tiles.csv) | One row per RWI tile (40,824), the main unit |
| [`data/derived/barangays.csv`](../data/derived/barangays.csv) | One row per barangay, the check |
| [`docs/data-quality.md`](data-quality.md) | How each source was parsed and joined, the column dictionary, and where the gaps sit. |

The data-quality headline:

- 7,284 of PCSO's 7,443 outlets (97.9%) are placed in a barangay, 133 more only at a town centre, and 26 (0.3%) cannot be placed.
- 331 GPS points disagree with the town in their address; they are kept and flagged.
- Population is the 2024 census: the 18 regional workbooks add up to the official 112,729,484 (with the 1,708 Filipinos counted at missions abroad), and 99.8% of barangays match a 2024 count by name.
- 99.4% of people live in a tile with an RWI value.
- BARMM is the weakest region for wealth (41 barangays without RWI) and has 15 outlets.

PCSO's outlet addresses can carry owners' names, so the outlet list itself is never committed; only counts per tile and per barangay are.

## 6. Results

### 6.1 RQ1: Outlets per person

> Are PCSO lotto outlets more or less common per person in poorer neighborhoods than in richer ones?

- The count of outlets per person increases with every step up the wealth quintile.
- This means that those in the poorest quintile have the least number of outlets per person (0.4) while those in the highest quintile have the most number of outlets (12.7).
- In fact, those in the highest quintile have 30x more outlets per person than those in the poorest quintile.
- The negative binomial regression model also supports this. It found that a tile one standard deviation richer contains 2.13x more outlets per person, holding the control variables constant.
- The logistic regression model found a similar pattern, with an odds ratio of 2.18

< insert chart here >

> Does the answer change once we account for province, how urban a place is, how many shops it has, and its road length?

- The counts change but the pattern is the same: richer neighborhoods have more outlets per person.
- Urban share barely moves the ratio from 2.45 to 2.13.
- Shop count is at 1.17.
- Roads is at 1.24.

< insert chart here >

![Figure 1. Outlets per 100,000 people by wealth quintile: national tiles against the barangays of Metro Manila, Metro Cebu and Metro Davao](../results/figures/quintile_rates.png)

*Figure 1. Outlets per 100,000 people by wealth fifth.
Each city is split by its own people, so its quintiles compare its poorer and richer parts with each other, not with the country.
No controls.*

### 6.2 RQ2: commerce

Most of the national gradient goes with where shops are.
The poorest fifth of tiles has 0.19 shops per 1,000 people, and 38% of its people live in urban cells; the richest fifth has 5.7 shops per 1,000, and 99.8% of its people are urban (`quintile_rates.csv`).
Adding shops to the model shrinks the wealth ratio from 2.13 to 1.17 (1.07-1.29), and adding road length as well leaves it at 1.24 (1.13-1.36) (`models.csv`).
So among tiles in the same province with the same shops and urban share, a tile one standard deviation richer still has about 1.2 times as many outlets per person: a small lean towards richer places, not poorer ones.

The checks agree.
Barangays give 1.50 with shops and 1.22 with shops and roads, and the presence model gives 1.59 with shops.
The tile ratio with shops barely moves when the model allows for spatial clustering (1.18), drops the GPS points that disagree with their address (1.16) or adds the outlets placed only at a town centre (1.17).
Whether shops are a confounder or the route by which wealth and outlets meet cannot be told apart here, so both readings stand: without shops, poorer Filipinos live with far fewer outlets around them; with shops, lotto still leans slightly towards richer places.

### 6.3 RQ3: within cities

The three cities do not share one pattern (Table 1, Figure 2).

*Table 1. Wealth rate ratio per national standard deviation of RWI, with 95% intervals.
Above 1 means more outlets per person in richer places.
Cities by barangay, with city and municipality intercepts and errors clustered by RWI tile (`models.csv`, `quintile_rates.csv`).*

| Scope | Outlets per 100k | Wealth only | + urban share | + shops | + shops and roads |
|---|---:|---:|---:|---:|---:|
| Philippines, tiles | 6.5 | 2.45 (2.23-2.69) | 2.13 (1.96-2.32) | 1.17 (1.07-1.29) | 1.24 (1.13-1.36) |
| Philippines, barangays | 6.5 | 2.82 (2.67-2.98) | 2.36 (2.22-2.52) | 1.50 (1.39-1.61) | 1.22 (1.14-1.30) |
| Metro Manila | 14.1 | 0.95 (0.82-1.09) | 0.95 (0.82-1.09) | 0.89 (0.75-1.04) | 0.93 (0.83-1.06) |
| Metro Cebu | 7.5 | 3.33 (2.09-5.31) | 2.34 (1.39-3.94) | 1.23 (0.65-2.33) | 1.16 (0.72-1.89) |
| Metro Davao | 5.5 | 4.65 (2.91-7.44) | 4.55 (2.59-8.00) | 3.47 (1.68-7.21) | 1.97 (1.20-3.21) |

**Metro Manila is flat.**
Every count variant sits between about 0.9 and 1.0, the presence models at about 1.2, and every interval includes 1, on barangays and on the 121 tiles alike.
Every wealth fifth of its barangays has between 12.5 and 15.2 outlets per 100,000 people, and the poorest fifth is, if anything, the highest (`quintile_rates.csv`).

**Metro Davao leans rich in every barangay variant**: 4.55 with urban share, 3.47 with shops, and 1.97 with shops and roads, all with intervals above 1.
Its rate climbs from 0.1 per 100,000 in the poorest fifth of barangays (one outlet among about 687,000 people) to 12.7 in the richest.
Its tiles agree (2.69 with urban share, 1.70 with shops); only the tile presence model is too imprecise to say either way (1.51, 0.68-3.34).

**Metro Cebu is unclear once shops are controlled.**
Its richer barangays have more outlets per person with urban share alone (2.34, 1.39-3.94), but with shops the ratio is 1.23 (0.65-2.33), and on its tiles 0.91 (0.74-1.13).
Among barangays with the same retail, richer and poorer ones cannot be told apart.
Its rate peaks in the fourth wealth fifth (12.8 per 100,000) and falls back in the richest (8.4).

![Figure 2. Wealth ratio by model variant with 95% intervals, one panel each for the Philippines, Metro Manila, Metro Cebu and Metro Davao](../results/figures/rate_ratios.png)

*Figure 2. The wealth ratio of every model variant, barangays and tiles, on a log scale.
The vertical line at 1 is no association.*

### 6.4 RQ4: road distance

Road access is unequal nationally, and the inequality favours richer places (Table 2).
The median person in the poorest fifth of tiles lives 11.5 km from an outlet by road, only 2% live within 2 km, and 4.4% have no road route to an outlet at all.
In the richest fifth the median is 0.6 km and 92% live within 2 km.
Metro Manila is the opposite case: the median is 0.4 to 0.5 km in every wealth fifth, and 99% of people live within 2 km of an outlet.
Metro Davao repeats the national ladder, and in Metro Cebu only the poorest fifth stands apart.

*Table 2. Median road distance to the nearest outlet, and the share of people within 2 km by road, by wealth fifth.
National quintiles by tile, city quintiles by each city's own barangays (`road_distance.csv`).*

| Scope | Poorest fifth | 2nd | 3rd | 4th | Richest fifth |
|---|---:|---:|---:|---:|---:|
| Philippines | 11.5 km, 2% | 5.4 km, 15% | 2.1 km, 48% | 0.9 km, 79% | 0.6 km, 92% |
| Metro Manila | 0.4 km, 99% | 0.5 km, 99% | 0.4 km, 99% | 0.4 km, 99% | 0.4 km, 99% |
| Metro Cebu | 4.5 km, 24% | 1.0 km, 82% | 0.7 km, 97% | 0.6 km, 97% | 0.8 km, 96% |
| Metro Davao | 12.5 km, 1% | 4.1 km, 23% | 1.6 km, 62% | 1.0 km, 88% | 0.7 km, 95% |

## 7. Discussion

### 7.1 Not an access story

The access version of "a tax on the poor" expects more outlets per person where people are poorer.
PCSO's lotto network shows the reverse nationally, and no lean towards the poor inside any of the three cities.
What outlets go with is commerce and urbanisation.
A lotto terminal is a counter in a shop, a mall or a market, so outlets sit where shops sit, and in the Philippines shops sit in towns and cities, which are richer than the countryside around them.
Once shops, roads and urban share are in the model, the national ratio falls from about 2.1 to about 1.2, and what is left still leans richer.
A plausible reading is that outlets are placed for foot traffic rather than aimed at poor neighbourhoods; the data are consistent with that, but cannot test it.

### 7.2 Why Metro Manila and Metro Davao differ

Metro Manila is urban throughout.
Almost all of its people (99.99%) live in urban cells, it has 6.0 shops per 1,000 people, and its barangays span a narrow band of wealth: a standard deviation of 0.20 RWI points, against one national standard deviation of 0.49 (`quintile_rates.csv`, notebook 3).
Outlets are close to everyone, rich or poor, so there is no gradient to find.
A one-standard-deviation contrast there also reaches beyond the region's own range of wealth, so the flat result says more about Manila's evenness than about any small lean the data cannot see.

Metro Davao is a different kind of place.
Republic Act No. 11708 draws it to take in Davao City's uplands, the southern municipalities and the Island Garden City of Samal as well as its urban core, so its barangays span a wide range of wealth (standard deviation 0.64) and a wide urban-rural range.
Its poorest fifth has 0.7 shops per 1,000 people, and only 38% of its people live in urban cells; its two richest quintiles have about 8 shops per 1,000 and are almost entirely urban.
Inside one boundary it repeats the national contrast between town and hinterland, and its gradient looks like the national one; the [Metro Davao](../results/figures/map_davao_bivariate.png) and [Metro Manila](../results/figures/map_ncr_bivariate.png) maps show the difference at a glance.
Urban share is in every model, but it is near 1 across the richer half of each city, so it cannot tell a town centre from a suburb, and whether Davao's gradient survives inside its urban core alone is untested (section 9).

Metro Cebu sits between the two (standard deviation 0.57).
Its [map](../results/figures/map_cebu_bivariate.png) splits into a dense urban core along the east coast, where the colours mix much as in Metro Manila, and a poorer, hilly interior with almost no outlets.
Its gradient goes with shops, and within the same retail it cannot be told apart from flat.

### 7.3 How this fits earlier studies

The Philippine result sits with the lottery side of the earlier studies, not the gaming-machine side.
Gaming machines and betting shops have been found to follow deprivation [[16](#ref-16), [17](#ref-17)].
Lottery retail has not: in New Jersey commercial land use was the strongest correlate and poverty turned negative [[18](#ref-18)], and in Massachusetts disadvantaged postcodes had no more agents or sales [[19](#ref-19)].
Here too outlets go with commerce, and with commerce held fixed the residual lean is towards richer places.
It adds a middle-income Asian case to a set of studies that had none.

### 7.4 What this cannot say

- **Access is not spending.**
  Fewer outlets near poorer people does not mean poorer people buy fewer tickets: they may buy where they work, shop or travel, and the outlets in a commercial centre serve people who live elsewhere.
- **Nothing here measures share of income.**
  A PHP 20 play is a larger share of a small income wherever it is bought, so the spending claim stays open and needs household budget data.
- **Association, not cause.**
  The ratios describe where outlets are relative to wealth, shops and towns; they do not say why PCSO and its agents put them there.
- **Lotto only.**
  The Small Town Lottery brought in PHP 31.76 billion of PCSO's PHP 62.35 billion gaming revenue in 2024 [[3](#ref-3)], and its booths are not published.
  These results cover the lotto network, not PCSO gaming as a whole.

## 8. Limitations

- **The wealth index's own error is not carried through the models.**
  The RWI is a modelled estimate with a per-tile error of 0.40 to 0.88 (mean 0.53), large next to Metro Manila's barangay standard deviation of 0.20 ([`docs/data-quality.md`](data-quality.md), notebook 3).
  The models treat it as exact, so their intervals are too narrow, most of all inside the cities, and error of this kind in a covariate tends to pull a ratio towards 1, which makes a flat result like Manila's weaker evidence than it looks.
  The RWI is also a 2021 relative score built partly from phone and connectivity data, not income or a poverty rate.
- **Shop coverage is uneven.**
  OpenStreetMap and Overture list 6.1 shops per 1,000 people in Metro Manila against 0.2 in BARMM and about 1.2 in Bicol and Soccsksargen, and both are better in richer, urban places ([`docs/data-quality.md`](data-quality.md)).
  The with-shops ratios rest on a control that is itself tied to wealth, and how far that biases them, and in which direction, is not known.
- **PCSO's outlet list is undated and may not be complete or current.**
  It lists 7,443 outlets against 6,494 agents at the end of 2023, more in every PCSO area, so it reads as a later list but may still hold closed outlets.
  The area figures for 2023 were read through a search index and not checked against the PDF (`pcso_cy2023_check.csv`).
  26 outlets could not be placed, 133 only at a town centre, and 331 GPS points disagree with their address; dropping or adding these moves the national ratios by 0.02 at most (`models.csv`).
- **2.4 km tiles are coarse inside cities.**
  Barangays in a city share wealth values (Metro Manila's 1,711 have most of their people in 113 tiles), so differences between neighbouring barangays inside one tile are invisible, and the errors are clustered by tile to allow for it.
  Barangay residuals cluster mildly nationally (Moran's I about 0.04; `spatial_checks.csv`); eigenvector refits leave the ratios where they were, but a full BYM2 model was not fitted.
- **The layers come from different years.**
  Outlets are a 2026 pull of an undated map, population is the 2024 census, wealth is a 2021 estimate, and shops and roads are October and November 2026.
  Outlets opened since 2024 in growing places would show there as more outlets per person.
- **Urban share cannot tell a town centre from a suburb**, since it is near 1 across the richer half of each city.
- **BARMM is thin**: 15 outlets for 5.7 million people and the weakest wealth coverage, so the national results say little about it.

## 9. Conclusion and future work

On the open data, PCSO's lotto outlets are not concentrated in poorer Philippine neighbourhoods.
Nationally they are far denser per person in richer places, mostly in step with where shops and towns are, with a small lean towards richer places beyond that.
Inside Metro Manila wealth makes no difference to outlet density, inside Metro Davao richer barangays have more, and inside Metro Cebu the lean goes with shops.
The poorest Filipinos live furthest from an outlet.
If the lottery is a tax on the poor in the Philippines, the case has to be made on spending, not on access.

What would take this further:

- **Carry the RWI error through**, by refitting on draws of the RWI from its per-tile error or with an errors-in-variables model, so the intervals reflect how uncertain wealth is.
- **Test Metro Davao's urban core on its own**, to see whether its gradient is a town-and-hinterland contrast or holds among urban barangays too.
- **Fit a full BYM2 model** in place of the eigenvector refits.
- **Read PCSO's 2023 agent figures off the annual report PDF** to close the coverage check.
- **Validate the RWI against Community-Based Monitoring System barangay poverty** where a city shares it.
- **Map the Small Town Lottery** if PCSO or local governments publish its booths.
- **Test the spending claim** with household budget data on lotto spending by income, the only way to answer the other half of the question.

## 10. How to reproduce

The steps, requirements and local preview are in the repository's [README](../README.md#how-to-reproduce).
In short, `./run_all.sh` collects every source, builds the two tables, runs the five notebooks and builds the web map, and on the same downloads it reproduces the committed tables byte for byte.
PCSO's outlet list is never committed, so outlet points appear only on a local build of the map.

Code is MIT licensed (see [LICENSE](../LICENSE)).
The data keep their own licences, listed in section 3 and under References, and the committed tables, figures and map tiles are built from them.
The wealth values come from the RWI, which is CC BY-NC 4.0, so anything built on them is for non-commercial use with attribution.

## References

1. <a id="ref-1"></a>Harris, J. *The US Lottery is a Lie.* YouTube, 8 March 2023. <https://www.youtube.com/watch?v=3Yn_3HqfV1w>
2. <a id="ref-2"></a>Berger, C. "America's poorest households spend 33 times more of their income on lottery tickets than the rich, data shows." Fortune, 4 April 2024. <https://fortune.com/2024/04/04/lottery-tickets-poor-rich-income-powerball-mega-millions-jackpot-odds-les-bernal-stop-predatory-gambling/>
3. <a id="ref-3"></a>Philippine Charity Sweepstakes Office. *Accomplishment Report 2024, Year-end.* 26 February 2025. <https://pcso-gov.ph/pcsofiles/transparency/12/Accomplishment%20Report%202024%20Yearend%20(20250226).pdf>
4. <a id="ref-4"></a>Philippine Charity Sweepstakes Office. "Lotto Outlets" map. <https://www.pcso.gov.ph/Maps/Outlets.aspx>
5. <a id="ref-5"></a>Inquirer. "7-Eleven operator celebrates 4,000-store milestone in PH." <https://business.inquirer.net/485115/7-eleven-operator-celebrates-4000-store-milestone-in-ph>
6. <a id="ref-6"></a>Statista. "Number of Jollibee stores." <https://www.statista.com/statistics/1479196/number-of-jolibee-stores/>
7. <a id="ref-7"></a>Batas Pambansa Blg. 42 (1979), amending RA 1169. LawPhil. <https://lawphil.net/statutes/bataspam/bp1979/bp_42_1979.html>
8. <a id="ref-8"></a>Republic Act No. 11223 (2019), Universal Health Care Act, Section 37(c). LawPhil. <https://lawphil.net/statutes/repacts/ra2019/ra_11223_2019.html>
9. <a id="ref-9"></a>Chi, G., Fang, H., Chatterjee, S. and Blumenstock, J. E. "Microestimates of wealth for all low- and middle-income countries." *PNAS* 119 (3), e2113658119, 2022. <https://doi.org/10.1073/pnas.2113658119>
10. <a id="ref-10"></a>Overture Maps Foundation. "Places guide." <https://docs.overturemaps.org/guides/places>
11. <a id="ref-11"></a>Gotway, C. A. and Young, L. J. "Combining incompatible spatial data." *Journal of the American Statistical Association* 97 (458), 632-648, 2002. <https://doi.org/10.1198/016214502760047140>
12. <a id="ref-12"></a>Mennis, J. "Generating surface models of population using dasymetric mapping." *The Professional Geographer* 55 (1), 31-42, 2003. <https://doi.org/10.1111/0033-0124.10042>
13. <a id="ref-13"></a>Riebler, A., Sørbye, S. H., Simpson, D. and Rue, H. "An intuitive Bayesian spatial model for disease mapping that accounts for scaling." *Statistical Methods in Medical Research*, 2016. <https://doi.org/10.1177/0962280216660421>
14. <a id="ref-14"></a>JICA and Metro Cebu Development and Coordinating Board. *The Roadmap Study for Sustainable Urban Development in Metro Cebu*, final report, summary. June 2015. <https://openjicareport.jica.go.jp/pdf/12235529.pdf>
15. <a id="ref-15"></a>Republic Act No. 11708 (2022), Metropolitan Davao Development Authority Act, Section 4. LawPhil. <https://lawphil.net/statutes/repacts/ra2022/pdf/ra_11708_2022.pdf>
16. <a id="ref-16"></a>Wheeler, B. W., Rigby, J. E. and Huriwai, T. *Health & Place* 12 (1), 86-96, 2006. <https://doi.org/10.1016/j.healthplace.2004.10.011>
17. <a id="ref-17"></a>Raisamo, S., Toikka, A., Selin, J. and Heiskanen, M. *BMC Public Health* 19, 1198, 2019. <https://doi.org/10.1186/s12889-019-7535-1>
18. <a id="ref-18"></a>Wiggins, L., Nower, L., Mayers, R. S. and Peterson, N. A. *Journal of Community Psychology* 38 (4), 486-496, 2010. <https://doi.org/10.1002/jcop.20376>
19. <a id="ref-19"></a>Pugh, Shirk and Volberg. *Journal of Gambling Studies* 42 (2), 663-683, 2026. <https://doi.org/10.1007/s10899-026-10475-6>

Data: PCSO's published outlet map; Meta / Data for Good Relative Wealth Index via the Humanitarian Data Exchange (CC BY-NC 4.0); WorldPop, University of Southampton (CC BY 4.0); PSA 2024 Census of Population; JRC GHSL Degree of Urbanisation (CC BY 4.0); OCHA COD-AB Philippines (CC BY-IGO); © OpenStreetMap contributors (ODbL); Overture Maps places (CDLA Permissive 2.0 and per-source terms).

## Appendix A. Code and pipeline

The code sits in one folder per phase under [`src/`](../src/), named after the phase script at the repo root that runs it (section 10).
The analysis is five narrative notebooks in [`notebooks/`](../notebooks/), committed with their outputs so each table and chart sits beside a short reading of it; their logic lives as functions in [`src/03_analyse/`](../src/03_analyse/) (`outlet_rates.py`, `count_models.py`, `road_distance.py`, `pcso_cy2023.py`, `charts.py`, `maps.py`), which the notebooks import; `pcso_background.py` draws the two background charts in section 1 from figures typed in from their sources.
Shared helpers are in [`src/shared/`](../src/shared/) (`common.py` paths and grid helpers, `analysis_samples.py` the analysis samples, `stats_tools.py` model and spatial helpers, `map_layers.py` the classes and colours the static and web maps share, `atlas.py` the story site's Atlas Grid style and its Riso data palette for every chart and map, with its fonts committed in `fonts/`, `palette_check.py` the palette's colour-blind checks, `run_notebook.py` the notebook runner `03_analyse.sh` uses, `setup.sh` the phase scripts' setup); each script adds that folder to Python's import path itself, so any script also runs on its own.

| Phase script | Step | Script | Writes |
|---|---|---|---|
| `01_collect_data.sh` | Download every source | [`download_sources.sh`](../src/01_collect_data/download_sources.sh), [`download_overture_places.py`](../src/01_collect_data/download_overture_places.py) | `data/raw/` (gitignored) |
| `02_build_tables.sh` | Read and check the 2024 census workbooks | [`read_census_2024.py`](../src/02_build_tables/read_census_2024.py) | `data/work/`, `data/derived/popcen2024_validation.json` |
| | Shop points and roads from OpenStreetMap | [`extract_osm_shops_and_roads.py`](../src/02_build_tables/extract_osm_shops_and_roads.py) | `data/work/` (gitignored) |
| | Barangays, 2024 census join, population and urban share on 100 m pixels, shops and roads per barangay | [`build_barangays.py`](../src/02_build_tables/build_barangays.py) | `data/work/`, `data/derived/barangays_summary.json` |
| | Parse PCSO GPS text, check it against the address, place outlets without coordinates | [`place_pcso_outlets.py`](../src/02_build_tables/place_pcso_outlets.py) | `data/work/` (outlet rows), `data/derived/pcso_geocoding.json` |
| | Tile and barangay tables, quality tables | [`build_tables.py`](../src/02_build_tables/build_tables.py) | `data/derived/` |
| `03_analyse.sh` | Outlets per 100,000 by wealth quintile, distributions, the PCSO CY2023 check | [`notebooks/01_descriptives.ipynb`](../notebooks/01_descriptives.ipynb) | `results/tables/`, `results/figures/` |
| | National count and presence models, spatial checks, sensitivities | [`notebooks/02_count_and_presence_models.ipynb`](../notebooks/02_count_and_presence_models.ipynb) | `data/work/` (model rows, residuals) |
| | Within cities: Metro Manila, Metro Cebu and Metro Davao, side by side with the national results | [`notebooks/03_within_cities.ipynb`](../notebooks/03_within_cities.ipynb) | `results/tables/`, `results/figures/` |
| | Road distance to the nearest outlet by wealth quintile | [`notebooks/04_road_distance.ipynb`](../notebooks/04_road_distance.ipynb) | `results/tables/` |
| | Static choropleth maps of outlet density beside wealth | [`notebooks/05_maps.ipynb`](../notebooks/05_maps.ipynb) | `results/figures/` |
| `04_build_map.sh` | Web map vector tiles | [`build_map_tiles.py`](../src/04_build_map/build_map_tiles.py) | `docs/map/data/` |
| | Web map colours, from `map_layers.py` | [`write_web_palette.py`](../src/04_build_map/write_web_palette.py) | `docs/map/palette.js` |

## Appendix B. Every figure and table

The interactive web map in [`docs/map/`](map/) shows the same layers, and more, to zoom and click through, at <https://earlcyu-petcircle.github.io/ph-lottery-outlets/map/> or locally as the [README](../README.md#how-to-reproduce) describes.
The static figures in [`results/figures/`](../results/figures/) can be read without it:

| Figure | What it shows |
|---|---|
| [`map_national_bivariate.png`](../results/figures/map_national_bivariate.png) | Every 2.4 km wealth tile by wealth third and outlet rate together: the national relationship on one map |
| [`map_national_rate_and_wealth.png`](../results/figures/map_national_rate_and_wealth.png) | Outlets per 100,000 people beside the Relative Wealth Index, on the same tiles |
| [`map_ncr_bivariate.png`](../results/figures/map_ncr_bivariate.png), [`map_ncr_rate_and_wealth.png`](../results/figures/map_ncr_rate_and_wealth.png) | The same two maps for Metro Manila's barangays |
| [`map_cebu_bivariate.png`](../results/figures/map_cebu_bivariate.png), [`map_cebu_rate_and_wealth.png`](../results/figures/map_cebu_rate_and_wealth.png) | The same two maps for Metro Cebu's barangays |
| [`map_davao_bivariate.png`](../results/figures/map_davao_bivariate.png), [`map_davao_rate_and_wealth.png`](../results/figures/map_davao_rate_and_wealth.png) | The same two maps for Metro Davao's barangays |
| [`quintile_rates.png`](../results/figures/quintile_rates.png) | Outlets per 100,000 people by wealth quintile: national tiles against the barangays of the three cities (Figure 1) |
| [`rate_ratios.png`](../results/figures/rate_ratios.png) | The wealth rate ratio of every model variant, one panel each for the country and the three cities (Figure 2) |
| [`pcso_gaming_revenue_2024.png`](../results/figures/pcso_gaming_revenue_2024.png) | PCSO gaming revenue in 2024 by game (section 1) |
| [`pcso_net_receipts_split.png`](../results/figures/pcso_net_receipts_split.png) | The statutory split of PCSO's net receipts (section 1) |

The tables in [`results/tables/`](../results/tables/):

| Table | What it holds |
|---|---|
| [`models.csv`](../results/tables/models.csv) | Every model's wealth rate ratio or odds ratio, interval, p-value and sample |
| [`coefficients.csv`](../results/tables/coefficients.csv) | Every coefficient of every model, controls included |
| [`spatial_checks.csv`](../results/tables/spatial_checks.csv) | Moran's I on each main model's residuals, before and after the spatial refits |
| [`quintile_rates.csv`](../results/tables/quintile_rates.csv) | Outlets, people, shops and urban share by wealth quintile, nationally and per city |
| [`distribution.csv`](../results/tables/distribution.csv) | Distributions of outlets, people, outlet rates, RWI and shops per tile and barangay |
| [`road_distance.csv`](../results/tables/road_distance.csv) | Road and straight-line distance to the nearest outlet by wealth quintile |
| [`pcso_cy2023_check.csv`](../results/tables/pcso_cy2023_check.csv) | PCSO's map against its CY2023 agent count, by PCSO area |

## Appendix C. Project history

The study was built in steps, each a pull request.
It began on 23 October 2026 as a first pass built on OpenStreetMap's lotto points ([#1](https://github.com/earlcyu-petcircle/ph-lottery-outlets/pull/1)), which hold only about 6% of PCSO's agents, so the design was redone around PCSO's own outlet map.
The final research design was settled on 31 October 2026 and shipped with the data collection ([#3](https://github.com/earlcyu-petcircle/ph-lottery-outlets/pull/3)).
The data analysis followed, first nationally and for Metro Manila ([#4](https://github.com/earlcyu-petcircle/ph-lottery-outlets/pull/4)), then for Metro Cebu and Metro Davao ([#5](https://github.com/earlcyu-petcircle/ph-lottery-outlets/pull/5)).
The results, discussion and clean-up came next, together, and turned the README into the finished paper ([#6](https://github.com/earlcyu-petcircle/ph-lottery-outlets/pull/6)).
Last came the one-page story site on GitHub Pages, at which point the paper moved from the README to this file.
