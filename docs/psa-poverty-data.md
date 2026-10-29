# PSA 2021 city and municipal poverty estimates: manual step

The municipal model can use the Philippine Statistics Authority's 2021 small-area poverty estimates as its wealth measure, next to the Relative Wealth Index.
The PSA website answers scripted downloads with a Cloudflare bot check (HTTP 403 to `curl`, and a "Performing security verification" page in an automated browser, tested 29 October 2026), so `src/fetch_data.sh` cannot fetch the file.
The pipeline runs without it and records `"psa": "not run ..."` in `data/derived/national_models.json`.

## The file needed

- **Release:** "PSA Releases the 2021 City and Municipal Level Poverty Estimates", <https://psa.gov.ph/statistics/poverty-sae> (README reference [14]).
- **Content:** poverty incidence among the population for 1,612 areas (114 cities, 1,484 municipalities and the 14 sub-municipalities of the City of Manila), each with its standard error, coefficient of variation and confidence interval.
- **Format:** the statistical tables attached to the release (Excel).

## Steps

1. Open the release page in a normal browser and download the statistical tables attached to it.
2. Take the 2021 poverty incidence among population and its coefficient of variation for every city and municipality.
3. Add up the City of Manila's 14 sub-municipalities into one row for the City of Manila, weighting each by its population (the boundary file treats Manila as one city).
4. Save the result as `data/manual/psa_sae_2021.csv` with exactly these columns:

   | Column | Meaning | Example |
   |---|---|---|
   | `psgc` | 10-digit PSGC code of the city or municipality, as text with leading zeros | `0102801000` |
   | `poverty_incidence` | Poverty incidence among population, 2021, in percent | `12.4` |
   | `cv` | Coefficient of variation of that estimate, in percent | `8.7` |

5. Re-run `./run_all.sh` (or `python src/barangay_models.py`).

## Matching codes

The boundaries are OCHA COD-AB version 3 (2025), whose city and municipality codes are `PH` plus the first seven digits of the current 10-digit PSGC: `0102801000` becomes `PH0102801` (Adams, Ilocos Norte).
PSGC codes changed after 2021 in Metro Manila, BARMM and a few other places, so some PSA rows may carry older codes.
The script reports `psa_rows` and `psa_matched` in `data/derived/national_models.json`.
If many rows fail to match, update their codes from the current PSA PSGC publication before re-running.

## What the script does with it

- Population-weighted poverty quintiles across cities and municipalities, quintile 1 being the highest poverty incidence.
- The full municipal NB2 model (urbanity, commerce, province fixed effects) with those quintiles in place of RWI quintiles.
- The same model on the cities and municipalities whose estimate has a coefficient of variation below 20%, the PSA's usual reliability threshold, as a sensitivity check.
- The rank correlation between poverty incidence and mean RWI, because agreement between a measured poverty rate and a modelled wealth index is itself a finding (review step 4).

The code path was tested with a synthetic file before release; no real PSA numbers are in this repository.
