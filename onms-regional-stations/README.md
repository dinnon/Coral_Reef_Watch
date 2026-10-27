# Coral Reef Watch regional station pilot

This is a separate, simpler data pull to compare with the ONMS boundary clipped CoralTemp SST series. It downloads NOAA's daily 5 km **regional** virtual station text files and writes a tidy daily CSV plus a monthly summary. Python standard library only.

```bash
python pull_stations.py FKNMS
python pull_stations.py                 # all five candidate regions
```

Run from this directory. Output is `data/<onms-code>/daily.csv` and `monthly.csv`. Re-running fetches each complete source file and replaces the corresponding CSV after parsing and validation; no raster backfill or cell inventory is needed. `complete_month=0` marks a partly reported current month **or a historical month with missing daily records**. The command prints the count and first dates of any gaps. It never invents missing observations; use only rows with `complete_month=1` for a historical monthly comparison. The monthly SST is the arithmetic mean of NOAA's **daily SST at the 90th-percentile HotSpot pixel**; NOAA can select a different pixel each day. The daily min and max columns describe the full CRW regional station footprint; their monthly means are **not** the spatial 10th–90th percentile band in the existing viewer. The NOAA SSTA column is likewise a NOAA station quantity and should not be presented as the existing viewer's 1991–2020 sanctuary anomaly.

## View the results

Double-click `index.html`: all five regional monthly series are embedded in the file, so there is no initial CSV selection, server, or NOAA connection required. The bundled regional daily data end October 24, 2026; October remains partial. Samoas is missing January 5, 2025 and March 24, 2026 in the NOAA source; those historical months remain excluded.

- Move the two handles on the shared timeline to choose the first and last month, or enter exact **From / To** months. A single month is supported. **All dates** resets the range. Changing the region resets to its full record; changing the measure keeps the selected dates.
- **Load all station CSVs** and **Open monthly.csv** remain available as optional overrides for the current session. An imported CSV is not permanently stored in the HTML. To save it into the next offline snapshot, place it in the correct data folder and run the offline rebuild below.
- The generated `index.html` can be hosted directly. Viewing the hosted HTML uses the saved snapshot; hosting does not itself refresh data from NOAA.
- The old FKNMS boundary viewer reads a different CSV schema. Use this viewer for the regional-station CSVs. Missing or incomplete months leave gaps in the line.

## Refresh and rebuild

```bash
python pull_stations.py            # download all five regions, then rebuild index.html
python pull_stations.py FKNMS      # update Florida Keys; embed all available local regions
python pull_stations.py --offline  # rebuild from existing CSVs, with no NOAA connection
```

The Python step now also writes `data/viewer_data.json` and regenerates `index.html` from `viewer_template.html`. Keep that template beside the script so future updates preserve the date controls and DHW styling. This small Python addition is necessary to keep an embedded snapshot current after each pull. The SST/DHW calculations and completeness rules are unchanged.

Defaults are relative to the script folder. `--output PATH` selects a different data folder, and `--viewer PATH` selects a different generated HTML path. A subset pull retains other local regions, which may have older source dates. `--offline` embeds whichever regional CSVs are available. Any download/parse failure prevents the subsequent HTML rebuild; the previous viewer remains available.

The **Peak daily DHW** measure uses the maximum of the reported daily station DHW values in each complete month. A dashed 4 °C-weeks line is NOAA's Bleaching Alert Level 1 DHW reference. NOAA also requires the **same day's** HotSpot to be at least 1°C; crossing 4 DHW alone does not establish an alert or observed bleaching. Peak DHW is embedded from `monthly.csv`; when rebuilding an older monthly CSV without that column, the script can derive the same monthly maximum from the companion `daily.csv`. The 4 DHW reference remains in front of the data with a white outline and bold label. SST and SST anomaly stay on their own Celsius scale.

The viewer is a standalone chart; it does not carry a sampling map because the points and ONMS boundary from the earlier raster pipeline describe a different geography.

| ONMS comparison label | CRW regional station | Source file | Fit |
| --- | --- | --- | --- |
| FKNMS | Florida Keys | `florida_keys.txt` | Geographic proxy, not FKNMS boundary |
| FGBNMS | Flower Garden Banks, Texas | `flower_garden.txt` | Geographic proxy, not FGBNMS boundary |
| NMSAS | Samoas | `samoas.txt` | Much broader than American Samoa sanctuary units |
| PNMS | Northwestern Hawaiian Islands | `nwhi.txt` | Broad regional proxy for Papahānaumokuākea |
| HIHWNMS | Main Hawaiian Islands | `hawaii.txt` | Broad regional proxy for sanctuary waters |
| GRNMS | No matching regional station identified | — | Retain boundary clipped series if included |

NOAA makes these station boundaries from reef-containing 5 km pixels plus a 20 km buffer, rather than the legal ONMS polygons. This pilot labels comparisons by ONMS code for convenience; captions must name the CRW station and its method. It does **not** claim a sanctuary-wide mean SST. NOAA labels the regional station product experimental. If this path becomes the published figure, a daily scheduled GitHub Action can call this script, publish the regenerated HTML and data outputs. We have not switched the existing chart or its workflow to this data source.

Sources: [station list and text files](https://coralreefwatch.noaa.gov/product/vs/data.php), [regional virtual station method](https://coralreefwatch.noaa.gov/product/vs/map.php), [gauge and SST time-series description](https://coralreefwatch.noaa.gov/product/vs/gauges/samoas.php).
