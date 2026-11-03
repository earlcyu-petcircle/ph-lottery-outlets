# Lottery as a tax on the poor? A spatial study of lotto outlets in the Philippines

Earl Yu, November 2026.
Open and published data only.

**Read it as a one-page story, with the interactive map: <https://earlcyu-petcircle.github.io/ph-lottery-outlets/>**

Are the Philippine Charity Sweepstakes Office's (PCSO) lotto outlets concentrated in poorer neighbourhoods?
On the open data, no.
Per person, outlets are about 30 times as common in the richest fifth of the country as in the poorest: 12.7 against 0.4 per 100,000 people.
Most of that gap goes with where shops and towns are, and among places with the same amount of retail, richer places still have about 1.2 times as many outlets per person.
Inside Metro Manila wealth makes no difference to outlet density, Metro Davao leans towards its richer barangays, and Metro Cebu's lean cannot be told apart from none once shops are held fixed.
The median person in the poorest fifth lives 11.5 km from an outlet by road, against 0.6 km in the richest.
Outlets follow commerce and urbanisation, not poverty.
That says nothing about who buys tickets or what share of their income they spend, and every result here is an association, not a cause.

![Wealth and outlet density together, Philippines: most of the country is poorer tiles with no outlet, and the tiles that are both richer and above the national outlet rate cluster in Metro Manila and the larger cities](results/figures/map_national_bivariate.png)

## Where things are

| Path | What it holds |
|---|---|
| [`docs/index.html`](docs/index.html) | The story site, served by GitHub Pages from `docs/` |
| [`docs/map/`](docs/map/) | The interactive web map, embedded in the site and at `<site>/map/` |
| [`docs/paper.md`](docs/paper.md) | The full paper: background, design, results, discussion, limitations, references and appendices |
| [`docs/data-quality.md`](docs/data-quality.md) | How each source was parsed and joined, the column dictionary, and where the gaps sit |
| [`results/tables/`](results/tables/), [`results/figures/`](results/figures/) | Every model, rate and distance table, and the static maps and charts |
| [`data/derived/`](data/derived/) | The two analysis tables: one row per 2.4 km wealth tile (`tiles.csv`) and per barangay (`barangays.csv`) |
| [`notebooks/`](notebooks/), [`src/`](src/) | The five analysis notebooks and the pipeline code ([Appendix A](docs/paper.md#appendix-a-code-and-pipeline) of the paper) |

## How to reproduce

Needs Python 3.12, `curl`, [tippecanoe](https://github.com/felt/tippecanoe) for the web map (`brew install tippecanoe`), about 1.2 GB of downloads and 5 GB of memory.
Nothing else is installed globally.
The 2024 census workbooks cannot be downloaded by script: fetch the 18 files by hand into `data/manual/popcen2024/` first, as [`docs/data-quality.md`](docs/data-quality.md#getting-the-files) describes.

```bash
git clone https://github.com/earlcyu-petcircle/ph-lottery-outlets.git
cd ph-lottery-outlets
./run_all.sh              # every phase below, in order
./run_all.sh --refresh    # same, but pull fresh PCSO, OpenStreetMap and Overture snapshots

./01_collect_data.sh      # downloads into data/raw/ (reuses them unless --refresh)
./02_build_tables.sh      # tile and barangay tables in data/derived/
./03_analyse.sh           # runs the five notebooks: tables, charts and maps in results/
./04_build_map.sh         # web map tiles in docs/map/data/
.venv/bin/python src/04_build_map/serve_map.py   # the site at http://localhost:8000/, the map at /map/
```

Each phase checks that the outputs it reads exist and names the phase to run if they do not, so the analysis can be rerun without collecting the data again.
The phases share one small helper, `src/shared/setup.sh`, which makes the local virtual environment and checks for tippecanoe.
Set `PYTHON=/path/to/python3.12` if `python3.12` is not on your path.
A run reuses anything already in `data/raw/`, so on the same downloads it reproduces the committed tables byte for byte; the table build takes about 2 minutes and the analysis about 10 minutes.
A `--refresh` run picks up a newer PCSO map, OpenStreetMap and Overture, so expect the counts to move.

The web map reads PMTiles files by HTTP range requests, so neither it nor the site opens from `file://`; `serve_map.py` is a small range-aware server for `docs/`.
The story site is hand-written HTML with no build step, and its numbers are typed in from `results/tables/`, so a rerun that moves the tables needs the site updated by hand.
Outlet points appear only in a local build of the map: PCSO's outlet list is never committed.

GitHub Pages serves the site from the `main` branch and the `/docs` folder (Settings, Pages, Deploy from a branch).

## Licence

Code is MIT licensed (see [LICENSE](LICENSE)).
The data keep their own licences, listed in the paper's [data sources](docs/paper.md#3-data-sources) and references, and the committed tables, figures and map tiles are built from them.
The wealth values come from the Relative Wealth Index, which is CC BY-NC 4.0, so anything built on them is for non-commercial use with attribution.
