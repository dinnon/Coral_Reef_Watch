# ONMS sanctuary SST explorer

An interactive monthly temperature chart and a reproducible CSV update script for five marine sanctuaries: PNMS, HIHWNMS, NMSAS, FGBNMS, and FKNMS. The package includes a user-provided `data/sst_monthly.csv` through August 2026 so the viewer can display data immediately. The single date slider chooses the first month shown; the chart always extends to the latest available month. This is a **fixed-pixel sampling indicator**, not a whole-sanctuary area mean. CoralTemp is a global SST product and can also support non-coral ocean locations with an appropriate sampling design. It uses only the Python standard library; the HTML viewer needs no JavaScript build step or API key.

## Expanded sampling for FKNMS and Papahānaumokuākea

The original script deliberately selected at most **two cells per boundary part**. The uploaded 1985–2026 CSV therefore has only 2 FKNMS and 4 PNMS cells every month. Its `coverage_pct=100` means only that those chosen cells have values; it is **not** geographic coverage. Keep this first series for comparison, but do not call it a sanctuary-wide SST mean.

The separate `build_spatial_sst.py` script inventories **every native 0.05° CoralTemp grid-cell center inside the actual ONMS polygons** for FKNMS and PNMS, including all polygon components that contain a grid center. It does not impose a sparse sampling stride. Each station is an eligible grid cell; a cell clipped by the boundary with its center outside is excluded. The monthly means weight valid cells by the cosine of latitude to approximate relative cell area. `coverage_pct` is the fraction of inventoried cells with valid observations that month, not sanctuary area or coral habitat coverage. Polygon parts with no interior cell are listed in the audit.

In IDLE, run these files in order from the existing `onms-sst` folder:

1. `plan_spatial_sst.py` writes `data/stations_spatial_v2.csv` and `data/spatial_v2_sampling_audit.json`, with **no SST download**. It uses the local boundary GeoJSON or obtains it from NOAA if absent. Open the viewer and use **Preview expanded cell plan** to compare them with the boundary, then check the audit's per-part counts. The chart still displays the original two- or four-cell series during this preview. If the proposed distribution needs adjustment, change the sampling design before the long download.
2. `build_spatial_sst.py` downloads monthly SST in spatial/time subsets. Each year and approximately 1° latitude band is checkpointed in `data/spatial_v2_chunks/`, so rerunning resumes past years and refreshes the current year. A stalled or failed NOAA request retains completed chunks. The historical download may take considerable time.
3. On successful completion it writes `stations_spatial_v2.csv`, `sst_monthly_spatial_v2.csv`, and `run_metadata_spatial_v2.json`. The viewer then uses the expanded series and locations for FKNMS and PNMS. The original `sst_monthly.csv`, original pixel CSV, and the other three sanctuaries are unchanged.

When updating an existing project folder, copy the new scripts, viewer, and documentation into it, and keep your existing `data/` directory with its boundary file and download checkpoints. A station plan from the earlier sparse version can be regenerated automatically if it has no SST checkpoints; if it does have checkpoints, the script stops and asks you to move that old `spatial_v2_chunks/` folder aside before starting a full-inventory backfill.

The expanded series uses NOAA monthly grid subset requests split into latitude bands. PNMS can contain many thousands of cells and the full historical backfill may require substantial download time and disk space. To avoid a single enormous pixel CSV, valid observations are stored in per-year and per-band CSV checkpoints listed in `data/spatial_v2_chunks/index.json`; the viewer links to that index. It is **not yet populated in this package** because live NOAA downloads are unavailable in this workspace. The proposed station counts and map placement require checking with your actual boundary file. This is a distinct time series; never append expanded cells to the two- or four-cell historical means. The existing scheduled Action still updates only the original series; adjust that workflow after reviewing the expanded results.

Before using the expanded curves in a report, inspect both cell maps and the number of polygon parts with zero interior cells, check the monthly valid/inventoried fraction for persistent land-masked cells, and compare the old versus expanded seasonal cycle and 1991–2020 anomalies. A future coral-habitat-specific indicator would need a reef footprint and a different selection rule. The inventory includes all native cell centers inside the supplied polygons, but is not a fractional-boundary-cell or reef-area-weighted sanctuary average.

## Quick start

From this folder, start the viewer:

```bash
python -m http.server 8000
```

Open http://localhost:8000 . The bundled summary CSV displays immediately. To update it from NOAA, run `python update_sst.py` before starting the server or while it is running. If your existing project has `stations.csv` and `sst_pixels_monthly.csv`, retain those files when replacing `index.html`; the updater will reuse them. In a fresh extraction of this package, the script first downloads NOAA boundaries, chooses fixed 0.05° grid-cell centers inside or near each sanctuary polygon, retrieves monthly SST from NOAA OceanWatch ERDDAP, and writes `data/stations.csv`, `data/sst_pixels_monthly.csv`, `data/sst_monthly.csv`, `data/download_progress.json`, and `data/run_metadata.json`. **A live network connection is required for updates.** The script prints its output path immediately; `stations.csv` appears once boundaries load. It requests recent SST first in five-year blocks, writes SST CSVs after every successful block, and marks each completed block in `download_progress.json`. OceanWatch is the first endpoint and NOAA CoastWatch West Coast is the fallback. The first backfill may take substantial time; later runs refresh the current time block and retain history. If interrupted, rerun it to resume uncompleted blocks. The viewer reads the CSV rather than requesting many ERDDAP series from every visitor's browser.

The location plot reads `data/stations.csv` and `data/sanctuary_boundaries.geojson`, then updates with the sanctuary selector. If you are replacing files in the folder where you already ran the pipeline, retain the existing station CSV. To add the actual NOAA sanctuary outlines without re-downloading any SST, run `export_boundaries.py` in IDLE (or `python update_sst.py --export-boundaries` in a terminal) once in that folder; it writes the GeoJSON to `data/`. The only network request is during this export, not during a visitor's map view. If you opened the viewer by double-clicking `index.html`, select the two local files in their respective file pickers. On a local web server, they load automatically. A fresh extraction has the summary CSV but no station or boundary files; run the updater or copy the files from your current project. The plot handles the date line and needs no map library or tiles. Outlines are the source polygons, and the 0.05° sampling cells are marked separately; neither visual coverage nor proximity alone establishes that the selected cells represent an area-wide sanctuary mean.

If your web host can run GitHub Actions, put these files at the repository root, enable workflow actions and grant workflow write access to the repository. `.github/workflows/update-sst.yml` attempts an update on the 5th and 20th of each month and commits the refreshed CSV. Deploy the folder with any static host (including GitHub Pages). You can also rerun `python update_sst.py` manually and republish the files. The browser reloads its hosted CSV hourly while open; **the browser does not independently pull new gridded data from NOAA**.

`python update_sst.py --refresh-stations` explicitly resamples the current boundary layer and rebuilds the entire pixel time series. Do this if ONMS boundaries change or you intentionally want to revise the sampling design; ordinary updates hold sampling locations fixed. Do not hand-edit the station file without rebuilding the series.

## Data flow and meaning

1. Boundary source: [ONMS FeatureServer](https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services/NMS_Boundaries_02032022/FeatureServer/0), referenced by [NOAA InPort](https://www.fisheries.noaa.gov/inport/item/37245). The script exports the selected source polygons into `sanctuary_boundaries.geojson` with the source URL and retrieval time. It does not replace them with a hand-drawn approximation. Selected stations have their source feature ID and coordinates in `stations.csv`. Polygon components are sampled at up to two interior 5 km grid centers; a tiny unit with no interior center gets a nearest-grid fallback explicitly marked `near_boundary`. Sample density is intentionally modest for very large sanctuaries. The design is for repeatable trends, not exhaustive spatial characterization.
2. SST source: [NOAA OceanWatch ERDDAP `CRW_sst_v3_1_monthly`](https://oceanwatch.pifsc.noaa.gov/erddap/griddap/CRW_sst_v3_1_monthly.html), with [NOAA CoastWatch West Coast `NOAA_DHW_monthly`](https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW_monthly.html) as a fallback. Both expose the CoralTemp v3.1 monthly mean `sea_surface_temperature` in °C; OceanWatch uses longitudes 0–360°, which the script converts from the signed longitude in `stations.csv`. Pixel observations and the actual endpoint's dataset ID are retained in `sst_pixels_monthly.csv`. NOAA's raw daily [CoralTemp product](https://coralreefwatch.noaa.gov/product/5km/index_5km_sst.php) is a nighttime satellite-based foundation SST estimate. The monthly series begins January 1985 and typically lags the daily product.
3. Aggregation: simple arithmetic mean across **valid selected station pixels** within each sanctuary and month. `n_valid`, `n_stations`, and `coverage_pct` expose missing pixel observations. Neither geographic area nor reef area is used as a weight. This sample is not suitable for describing an entire sanctuary's temperature range; inspect `stations.csv` on a map before scientific use.
4. Anomaly: for each sanctuary and calendar month, the mean of that month's available sanctuary sample means from 1991–2020 (at least 20 years needed) is subtracted from its observed monthly mean. This is *our computed 1991–2020 anomaly*, not the CRW bleaching-specific SST anomaly product. Annual means in the viewer require all 12 months within the selected date range.

## QA to perform after a live first run

- Map station coordinates against the ONMS polygons and coastal land, especially small units and the date line at PNMS. A station with no valid SST may fall on a masked land grid cell.
- Confirm each sanctuary has enough valid pixels and that `coverage_pct` is stable. Do not infer a warming trend when the composition of valid pixels changes substantially.
- Compare one station-month SST with the same ERDDAP point query; compare a sampled recent month to NOAA's monthly composite map.
- NOAA blends different input analyses over the historical period. Keep the product version and note source changes in interpretation; trends are environmental indicators, not local in-water thermometer measurements.

## CSV columns

`sst_monthly.csv`: `month`, `sanctuary`, `mean_sst_c`, `min_sst_c`, `max_sst_c`, `n_valid`, `n_stations`, `coverage_pct`, `anomaly_c`, `source_dataset`, `spatial_method`.

`sst_pixels_monthly.csv`: `month`, `sanctuary`, `station_id`, `latitude`, `longitude`, `sst_c`, `source_dataset`.

`stations.csv`: `sanctuary`, `station_id`, `latitude`, `longitude`, `spatial_relation`, `boundary_objectid`, `geometry_source`.

## Live connection versus published snapshot

The **Python update is live against NOAA** each time it runs. The dashboard's CSV is a dated snapshot that can be served quickly and used offline after download. This split avoids a large number of browser requests, cross-origin problems, and failed visits when NOAA's ERDDAP is slow. The date badge makes the snapshot age visible. For a future server-backed tool, the same script can write CSV to object storage instead of committing to Git.
