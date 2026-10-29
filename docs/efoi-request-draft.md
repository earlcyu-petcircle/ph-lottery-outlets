# Draft eFOI request to the PCSO: authorised lotto outlet list

**Status: draft, not filed.**
Earl files this himself through the eFOI portal.
Nothing in this repository submits it or contacts the PCSO.

## Why this request matters

The study's main limit is the outcome data.
OpenStreetMap and Overture between them hold about 505 lotto outlets, about 11% of the roughly 4,600 the PCSO reported in October 2023, and the missing outlets are concentrated in poorer, less-mapped regions (README section 3).
Every peer-reviewed outlet-location study the literature review found uses a complete official register instead.
A PCSO list with addresses would turn this from a sample whose gaps follow wealth into a census, and would let the barangay model in [`src/barangay_models.py`](../src/barangay_models.py) run unchanged on the true outcome.

## Before filing

1. Check the existing request "List of lotto outlets in the Philippines as of December 31, 2023" on the eFOI portal (README reference [16]).
   If the PCSO released a file there, download it first; this request may then only need the fields or the date that release lacks.
2. Check the PCSO's own FOI page and People's FOI Manual for the receiving officer, any form the agency asks for, and the exceptions it applies.
3. Have a government ID ready; the portal asks for identity verification.

## Where to file

- **Portal:** eFOI, <https://www.foi.gov.ph>, agency "Philippine Charity Sweepstakes Office (PCSO)".
- **Basis:** Executive Order No. 2, s. 2016 (Freedom of Information in the Executive Branch), and the PCSO's People's FOI Manual.

## Request text

Copy from here into the portal.

---

**Title:** List of authorised lotto outlets with addresses, as of 31 December 2025

**Request:**

I request a list of all PCSO-authorised lotto outlets (online lottery terminals, including those selling Lotto and digit games), as of 31 December 2025 or the latest date available.

For each outlet, please include the following fields where the PCSO holds them:

1. Outlet or retailer code, or another identifier unique to the outlet.
2. Business or trade name of the outlet (not the name of an individual owner).
3. Full address: street, barangay, city or municipality, and province.
4. PSGC code of the barangay or city/municipality, if recorded.
5. Latitude and longitude, if recorded.
6. PCSO branch or regional office responsible for the outlet.
7. Status as of the reference date (active, suspended or closed), and the date the outlet was authorised.
8. Number of terminals at the outlet.
9. Type of host location, if recorded (for example sari-sari store, mall kiosk, supermarket, stand-alone outlet).

If a full snapshot as of 31 December 2023 also exists, please include it, so the list can be compared with the figure of about 4,600 outlets the PCSO reported in October 2023.

If the PCSO holds a list of Small Town Lottery (STL) authorised agent corporations with the cities and municipalities each is authorised to operate in, please include it as a separate table.
Locations of individual STL booths or agents are welcome if the PCSO holds them, but are not essential.

Please redact or omit the names and personal details of individual outlet owners or agents.
Business names and outlet addresses are enough for this request.

**Preferred format:** a machine-readable spreadsheet (CSV or XLSX), one row per outlet.
A PDF table is acceptable if a spreadsheet is not available.

**Purpose:** Non-commercial academic-style research on the geography of lottery access in the Philippines.
The research tests whether lotto outlets are more common, per person, in poorer neighbourhoods, using census population and official poverty estimates.
No peer-reviewed study of this question exists for the Philippines.
Results will be published only as counts by barangay, city or municipality and as maps of outlet locations; no personal information will be published.

---

## Notes for after a response

- **Partial release.** If the PCSO releases only city or municipal counts, the municipal model still runs: put the counts in place of `lotto_union` at the municipality level in [`src/barangay_models.py`](../src/barangay_models.py) section 5.
- **Geocoding.** If the list has addresses but no coordinates, geocode to barangay by matching the barangay and municipality names to the COD-AB boundaries (the same name normaliser as [`src/barangays.py`](../src/barangays.py)), not to street points; barangay is the unit of analysis.
- **Validation.** Compare the official list with the 505 open-data outlets: the share of open outlets matched, and the official count per region against README section 3.1.
  That is the direct measure of how biased the open record is.
- **Do not commit the raw list** if it carries anything beyond business names and addresses; commit only derived counts.
