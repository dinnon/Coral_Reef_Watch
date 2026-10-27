# Coral Reef Watch regional station pilot

This is a separate, simpler data pull to compare with the ONMS boundary clipped CoralTemp SST series. It downloads NOAA's daily 5 km **regional** virtual station text files and writes a tidy daily CSV plus a monthly summary. Python standard library only.

```bash
python pull_stations.py FKNMS
python pull_stations.py                 # all five candidate regions
```

Run from this directory. Output is `data/<onms-code>/daily.csv` and `monthly.csv`. Re-running fetches each complete source file and replaces the corresponding CSV after parsing and validation; no raster backfill or cell inventory is needed. `complete_month=0` marks a partly reported current month **or a historical month with missing daily records**. The command prints the count and first dates of any gaps. It never invents missing observations; use only rows with `complete_month=1` for a historical monthly comparison. The monthly SST is the arithmetic mean of NOAA's **daily SST at the 90th-percentile HotSpot pixel**; NOAA can select a different pixel each day. The daily min and max columns describe the full CRW regional station footprint; their monthly means are **not** the spatial 10th–90th percentile band in the existing viewer. The NOAA SSTA column is likewise a NOAA station quantity and should not be presented as the existing viewer's 1991–2020 sanctuary anomaly.

## View the results

- Double-click `index.html`. Pick the region, click **Open monthly.csv**, and select that region's `data/<onms-code>/monthly.csv`. Repeat for another region; the viewer remembers files selected during that browser session. This works without a local server.
- Or run `python -m http.server 8000` from this folder, then open `http://localhost:8000/`. The viewer fetches the selected region's CSV automatically. This is also how it works on a static host if `index.html` and the `data/` directory are published together.
- The old FKNMS boundary viewer reads a different CSV schema. Use this new `index.html` for the regional-station CSVs. The one start slider controls the first month shown. Incomplete months leave gaps in the line; hovering identifies them.

The viewer is a standalone chart; it does not carry a sampling map because the points and ONMS boundary from the earlier raster pipeline describe a different geography.

| ONMS comparison label | CRW regional station | Source file | Fit |
| --- | --- | --- | --- |
| FKNMS | Florida Keys | `florida_keys.txt` | Geographic proxy, not FKNMS boundary |
| FGBNMS | Flower Garden Banks, Texas | `flower_garden.txt` | Geographic proxy, not FGBNMS boundary |
| NMSAS | Samoas | `samoas.txt` | Much broader than American Samoa sanctuary units |
| PNMS | Northwestern Hawaiian Islands | `nwhi.txt` | Broad regional proxy for Papahānaumokuākea |
| HIHWNMS | Main Hawaiian Islands | `hawaii.txt` | Broad regional proxy for sanctuary waters |
| GRNMS | No matching regional station identified | — | Retain boundary clipped series if included |

NOAA makes these station boundaries from reef-containing 5 km pixels plus a 20 km buffer, rather than the legal ONMS polygons. This pilot labels comparisons by ONMS code for convenience; captions must name the CRW station and its method. It does **not** claim a sanctuary-wide mean SST. NOAA labels the regional station product experimental. If this path becomes the published figure, a daily scheduled GitHub Action can call this script, commit changed CSVs, and explicitly publish the site. We have not switched the existing chart or its workflow to this data source.

Sources: [station list and text files](https://coralreefwatch.noaa.gov/product/vs/data.php), [regional virtual station method](https://coralreefwatch.noaa.gov/product/vs/map.php), [gauge and SST time-series description](https://coralreefwatch.noaa.gov/product/vs/gauges/samoas.php).
