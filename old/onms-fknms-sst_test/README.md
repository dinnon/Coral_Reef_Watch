# FKNMS CoralTemp SST: one sanctuary pilot

This is a focused restart for **Florida Keys National Marine Sanctuary (FKNMS)**. It builds a station inventory from the NOAA sanctuary boundary and extracts NOAA CoralTemp monthly SST for **every native 0.05° cell center inside that boundary**. It contains no old two-cell series and does not process PNMS or the other sanctuaries.

## Run

1. Unzip into a **new folder**. With Python 3.10+ and an internet connection, run `run_sst.py` from IDLE (F5), or run `python run_sst.py` in a terminal from this folder. No extra Python packages are needed.
2. The script prints where it writes `data/`, the FKNMS station count, and a progress line before **each NOAA request**. It starts with the newest three-month block, then works backward to 1985. Each completed quarter and latitude band saves a CSV and `.months.json` checkpoint in `data/chunks/`. If both NOAA endpoints fail on a completed quarter, it tries individual months. This first backfill can still take time.
3. If it stops, rerun the same command in the same folder. Completed quarters are kept; the active quarter refreshes for newly released months. To review the inventory without requesting SST, use `python run_sst.py --plan-only`.
4. When it finishes, run `python -m http.server 8000` in this folder and open `http://localhost:8000`. The viewer reads the completed FKNMS summary, station CSV, and boundary GeoJSON. It deliberately does not display the old two-cell series.

If your earlier six-site attempt already saved `data/sanctuary_boundaries.geojson`, you may copy **that file alone** into this new `data/` folder to avoid refetching the NOAA boundary. The script will select FKNMS from it. Do not copy the old station, pixel, summary, or checkpoint files into this pilot: their spatial selection and checkpoint format may differ.

## Files and quality checks

- `data/sanctuary_boundaries.geojson`: source polygon and retrieval time.
- `data/stations.csv`: all in-boundary native-grid centers; `data/sampling_audit.json`: total and per-polygon-part counts. A part with zero centers is flagged.
- `data/chunks/FKNMS_YEAR_qN_latNNN.csv`: valid per-cell monthly SST and exact source dataset; matching `.months.json` files also record slices with no valid SST. `data/chunks/index.json` lists pixel files.
- `data/sst_monthly.csv`: monthly cosine(latitude)-weighted mean, min/max, valid/selected count, coverage percentage, and same-calendar-month 1991–2020 anomaly; `data/run_metadata.json`: source and selection hash.

The summary is written only after **all** quarters and latitude bands finish. For a given quarter, only months returned in every latitude band are published. A month with no valid cell values is retained with `n_valid=0` and blank SST. `coverage_pct` measures valid cells among selected centers, not percent sanctuary area. This is sea surface temperature, not reef-depth temperature, coral habitat coverage, bleaching stress, or an exact boundary-area-weighted mean.

Before using the series, check the station count and map, missed polygon components, monthly valid fractions, and several individual cells against NOAA. Once the FKNMS run and figures look right, we can repeat the same template for each other sanctuary and then schedule incremental updates.

Sources: [NOAA ONMS boundaries](https://www.fisheries.noaa.gov/inport/item/37245), [NOAA OceanWatch CoralTemp monthly SST](https://oceanwatch.pifsc.noaa.gov/erddap/griddap/CRW_sst_v3_1_monthly.html), and [NOAA CoastWatch monthly SST fallback](https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW_monthly.html).
