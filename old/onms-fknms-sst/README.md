# FKNMS sanctuary-wide CoralTemp SST

This is a focused restart for **Florida Keys National Marine Sanctuary (FKNMS)**. It builds a station inventory from the NOAA sanctuary boundary and extracts NOAA CoralTemp monthly SST for **every native 0.05° cell center inside that boundary**. It contains no old two-cell series and does not process PNMS or the other sanctuaries.

The included NOAA run covers **January 1985–August 2026**. It selected **416** in-boundary cells, with **414** valid SST values per published month. The full 1991–2020 same-calendar-month anomaly is included. Run the script again to check for newly released months.

## Run

1. Unzip into a **new folder**. With Python 3.10+ and an internet connection, run `run_sst.py` from IDLE (F5), or run `python run_sst.py` in a terminal from this folder. No extra Python packages are needed.
2. The script prints where it writes `data/`, the FKNMS cell count, and a progress line before **each NOAA request**. It starts with the newest three-month block, then works backward to 1985. Each completed quarter and latitude band saves a CSV and `.months.json` checkpoint in `data/chunks/`. After all bands for a quarter finish, it publishes the available sanctuary-wide monthly series. You can view recent months while older quarters are still being pulled. If both NOAA endpoints fail on a historical quarter, it tries individual months.
3. If it stops, rerun the same command in the same folder. Completed quarters are kept; the active quarter refreshes for newly released months. To review the inventory without requesting SST, use `python run_sst.py --plan-only`.
4. Run `python -m http.server 8000` in this folder and open `http://localhost:8000`. The viewer loads the current FKNMS summary, cell CSV, and display boundary automatically; reload the page as new quarters finish. You can also double-click `index.html` and use **Open monthly summary CSV** to select `data/sst_monthly.csv` directly. To see the sampling footprint from a local file, also choose `data/stations.csv` and `data/boundary_preview.geojson`. The viewer displays the number of selected and valid cells, so an older two-cell CSV is identifiable if selected manually.

For a fresh historical rebuild, `python backfill_netcdf.py` is faster because it requests five-year raster subsets and writes the **same** quarter checkpoints. It requires SciPy (`python -m pip install scipy`). It resumes without overwriting completed checkpoints. Run `python run_sst.py` afterward to refresh the newest available quarter. The NetCDF route was checked against CSV for all 1,104 valid cell-months in one 2021 latitude band.

If your earlier six-site attempt already saved `data/sanctuary_boundaries.geojson`, you may copy **that file alone** into this new `data/` folder to avoid refetching the NOAA boundary. The script will select FKNMS from it. Do not copy the old station, pixel, summary, or checkpoint files into this pilot: their spatial selection and checkpoint format may differ.

## Files and quality checks

- `data/sanctuary_boundaries.geojson`: source polygon and retrieval time.
- `data/boundary_preview.geojson`: simplified display outline for a responsive, offline map. It is **not** used for cell selection. The detailed source geometry is large (about 84 MB unpacked).
- `data/stations.csv`: all in-boundary native-grid centers; `data/sampling_audit.json`: total and per-polygon-part counts. A part with zero centers is flagged.
- `data/chunks/FKNMS_YEAR_qN_latNNN.csv`: valid per-cell monthly SST and exact source dataset; matching `.months.json` files also record slices with no valid SST. `data/chunks/index.json` lists pixel files.
- `data/sst_monthly.csv`: monthly cosine(latitude)-weighted sanctuary mean, unweighted cell 10th and 90th percentiles, min/max, valid/selected count, coverage percentage, and same-calendar-month 1991–2020 anomaly; `data/run_metadata.json`: source, selection hash, and backfill status.

Each quarter is published only after **all its latitude bands finish**. The summary contains only months returned in every band of a completed quarter. A month with no valid cell values is retained with `n_valid=0` and blank SST. `coverage_pct` measures valid cells among selected centers, not percent sanctuary area. The shaded band is the distribution of valid monthly cell values, not a confidence interval. Anomaly is blank until at least 20 same-month reference years from 1991–2020 have been retrieved. This is sea surface temperature, not reef-depth temperature, coral habitat coverage, bleaching stress, or an exact boundary-area-weighted mean.

Before using the series, check the station count and map, missed polygon components, monthly valid fractions, and several individual cells against NOAA. Once the FKNMS run and figures look right, we can repeat the same template for each other sanctuary and then schedule incremental updates.

Sources: [NOAA ONMS boundaries](https://www.fisheries.noaa.gov/inport/item/37245), [NOAA OceanWatch CoralTemp monthly SST](https://oceanwatch.pifsc.noaa.gov/erddap/griddap/CRW_sst_v3_1_monthly.html), and [NOAA CoastWatch monthly SST fallback](https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW_monthly.html).
