# SST sampling decision record — 25 September 2026

## Why the prototype is being revised

`update_sst.py` selects at most two 0.05° grid centers per polygon part. Its
first complete CSV contains 2 FKNMS cells and 4 PNMS cells in each of 500
months (January 1985 through August 2026). All selected cells have valid data,
so the original `coverage_pct=100` is **data completeness for selected cells**,
not geographic coverage of either sanctuary.

With only two FKNMS cells, the monthly mean is the midpoint of those two
temperatures. Across the 500 months, their absolute difference averages
1.13°C; the January difference averages 2.60°C and the largest difference is
4.58°C (February 2026). The original curve remains a valid fixed-location
indicator, but a sanctuary-wide interpretation is not supported.

## Expanded spatial sample (version 2)

The independent pipeline inventories **every native 0.05° CoralTemp grid center**
inside each NOAA ONMS boundary polygon for FKNMS and PNMS. No subsampling
stride is applied. A boundary piece without a grid-cell center has zero
stations; clipped cells with centers outside the boundary are not included.
The exact station counts and per-component counts are calculated locally from
the user's boundary GeoJSON by `plan_spatial_sst.py`, with no SST download.
They are not known from the uploaded summary CSV. Monthly valid cells are
weighted by `cos(latitude)` to approximate equal-angle grid-cell area. The
1991–2020 baseline and anomalies are recalculated. `coverage_pct` means
valid/inventoried cells, not geographic or coral habitat coverage. The result
is a sanctuary-water SST indicator, not reef-depth temperature or bleaching
heat stress. Check the inventory map and the audit before interpreting it.

## Reproducibility and migration

- The original CSVs and `stations.csv` remain intact for comparison.
- `stations_spatial_v2.csv` identifies every in-polygon grid center.
- `spatial_v2_sampling_audit.json` records selected counts and counts for each
  polygon component; `spatial_v2_chunks/` checkpoints each year and latitude band; `index.json` lists every pixel CSV.
- Only after all years finish are `sst_monthly_spatial_v2.csv` and
  `run_metadata_spatial_v2.json` published.
- The viewer uses version 2 for FKNMS and PNMS only when the complete-history
  metadata and series exist; otherwise it warns that the original series has
  two or four cells. The other three sanctuaries still use the prototype.
- The current scheduled Action updates the prototype only. Automation of the
  new pipeline should follow inspection of the new geography and trends.

**Sources:** [NOAA Coral Reef Watch CoralTemp monthly grid](https://oceanwatch.pifsc.noaa.gov/erddap/griddap/CRW_sst_v3_1_monthly.html),
[NOAA ONMS sanctuary boundaries](https://www.fisheries.noaa.gov/inport/item/37245),
and the original `sst_monthly.csv` supplied for this project.
