# NOAA Coral Reef Watch named reef sites — expanded pilot

## Open the results

Unzip this entire folder and double-click **index.html**. The HTML includes the real data and works offline; no CSV upload, server, API key, or map tiles are required.

- Choose among **nine groups / 218 named sites**: Flower Garden Banks, USVI, Florida, Puerto Rico, Samoan Islands, Guam, CNMI (two groups), and the main Hawaiian Islands.
- Select a station on the map, in the list, or in the Series menu. **Regional average** shows the mean across distinct named site pixels. An individual site view also shows that average as a gray comparison line.
- Choose monthly mean SST, monthly mean NOAA SST anomaly, or monthly peak daily DHW. Use the two handles on the shared timeline, or the From/To month fields, to select any date window (including one month). All dates resets the range. Hover for values and coverage. The displayed-series CSV export follows the selected window.
- **Download displayed series CSV** exports the chosen chart. Complete tables are also in `data/`.
- **Open updated data JSON** loads a replacement `data/viewer_data.json` in a previously opened viewer.

## Coverage and group definitions

This version includes every single-pixel site linked from the 12 named-site pages in NOAA's [Single-Pixel Stations list](https://coralreefwatch.noaa.gov/product/vs/map.php), checked October 23, 2026. The four main Hawaiian island pages are combined into one group. `regions.json` is the explicit list of page URLs; each run discovers all site files on those pages, so new sites on a configured page are included automatically. A newly published region/page still needs to be added to the configuration.

| Region ID for the command line | Group | Named sites |
| --- | --- | ---: |
| `fgb` | Flower Garden Banks | 17 |
| `usvi` | US Virgin Islands | 6 |
| `florida_keys` | Florida: Keys, Dry Tortugas and southeast Florida | 19 |
| `puerto_rico` | Puerto Rico | 16 |
| `samoas` | Samoan Islands | 26 |
| `guam` | Guam | 28 |
| `saipan_tinian_aguijan` | CNMI: Saipan, Tinian and Aguijan | 27 |
| `rota` | CNMI: Rota | 10 |
| `hawaii` | Main Hawaiian Islands: Kauai/Niihau, Oahu, Maui Nui, Hawaii | 69 |

These are NOAA site groups, **not sanctuary boundary selections**. In particular, the Florida group extends beyond the Keys, and the Hawaii mean includes sites across the main islands. Papahānaumokuākea / Northwestern Hawaiian Islands and Gray's Reef have no named-site page in the verified list and are not included; their regional or raster workflows remain separate. No regional-summary or legacy 50 km data are substituted.

### Source freshness

The October 23, 2026 build contains daily records from **January 1, 1985 through October 22, 2026 for all 218 sites**. Each group has **501 complete monthly SST values (January 1985–September 2026)**. October 2026 is partial and is not used as a complete monthly value.

The bundled `data/coverage.csv` reports the number of named sites, unique pixels, earliest/latest source end dates, and first/last complete SST months in every group. Per-site source dates and URLs are in `stations.csv` and the viewer. Source coverage can lag differently across groups: a successful download cannot add dates that NOAA has not published. Full available histories are retained from 1985; incomplete calendar months remain blank.

## Update / reproduce

Python 3.10+; standard library only. From this folder:

```bash
python pull_sites.py
```

On Windows, `py pull_sites.py` also works. The command fetches all configured NOAA named-site index pages, discovers all their single-pixel text files, validates the records, writes monthly datasets, and rebuilds `index.html`. Internet access to `coralreefwatch.noaa.gov` is required. Run it monthly manually; the same command can later run in GitHub Actions. No schedule or deployment is enabled in this package.

To rebuild the bundled outputs without downloading anything:

```bash
python pull_sites.py --offline
```

To build only one configured region:

```bash
python pull_sites.py --regions fgb
```

That makes the viewer contain only the requested region(s). `regions.json` lists the NOAA single-pixel index page(s) for each region. New groups can be added there when their NOAA single-pixel pages use the same file schema. The template supports multiple page URLs per region, as used for Hawaii. The viewer dynamically builds the region/site menus and map from the generated bundle; no site list is hard-coded in the viewer.

### Download controls and recovery

```bash
python pull_sites.py --list-regions
python pull_sites.py --regions florida_keys fgb samoas hawaii
python pull_sites.py --workers 2
python pull_sites.py --cache-hours 24
python test_pipeline.py
```

By default, four site files are downloaded concurrently (maximum eight), with retries for transient failures. All requested pages and sites must validate before data outputs are published. The normal command refreshes every source. After an interrupted pull, `--cache-hours 24` reuses files successfully downloaded in the last 24 hours and fetches the rest; it deliberately allows sources to be up to 24 hours old. `--offline` never accesses NOAA and requires the matching cached pages and files. Do not run concurrent builds in the same folder.

A subset run rebuilds the viewer and coverage report with only the requested groups; existing CSV directories for other groups are retained and may be older. A plain `python pull_sites.py` restores the all-group viewer. Site additions/removals change the group's mean membership, including historical means on a subsequent rebuild; compare `stations.csv` between archived builds before publishing trend comparisons.

## Outputs

- `index.html`: generated, self-contained map and chart; can be hosted as an HTML figure.
- `viewer_template.html`: editable viewer source; the script embeds data here on each run.
- `data/coverage.csv`: compact inventory and data freshness report for the current build.
- `data/viewer_data.json`: all station metadata, monthly site series, and regional monthly means.
- `data/<region>/stations.csv`: names, coordinates, source URLs and hashes, date coverage, and inclusion in the regional average.
- `data/<region>/station_monthly.csv`: all named site monthly values in one tidy CSV per region.
- `data/<region>/region_monthly.csv`: the regional means, station minima/maxima, and valid/expected pixel counts for each measure.
- `data/<region>/daily/*.csv`: parsed NOAA daily SST, SSTA, HotSpot, and DHW values for each site.
- `cache/`: downloaded NOAA source text and index pages, retained for offline rebuilding.

## Decisions and interpretation

1. **Fixed named sites:** each record comes from NOAA's single-pixel product, using the site's latitude and longitude from its file. This is separate from the regional `SST@90th_HS` product. The pilot includes every site listed on each configured page. It does not clip sites to ONMS boundaries.
2. **Monthly SST:** arithmetic average of daily values within each calendar month, requiring all calendar days to have valid SST. The same rule is applied independently to anomaly and DHW. Missing sentinels remain missing. Partial month values are blank and coverage counts remain available. Dates must be strictly ordered and unique.
3. **Regional mean:** equal weight per distinct coordinate pair, averaging complete site monthly values. Site aliases at the same coordinate pair are counted once. The regional mean is only published when every selected distinct pixel has a complete value for that metric in that month. This is the mean of selected reef sites, not an ONMS area average. It is not a probability sample of all sanctuary waters.
4. **Anomaly:** NOAA's reported daily SSTA is averaged by month, then across sites; each site uses NOAA's climatology. We do not calculate a new 1991–2020 baseline.
5. **DHW:** the site chart displays each month's maximum of NOAA's reported daily DHW. The regional chart averages those site maxima, which may occur on different days. That average is descriptive; it is not NOAA's regional DHW algorithm or an alert classification. The 4 °C-weeks reference appears only for individual sites; NOAA Alert Level 1 also requires concurrent HotSpot ≥1°C. No observed coral bleaching is inferred from the line alone.
6. **Mapping:** a self-contained longitude/latitude plot with selectable 0.05° × 0.05° cell footprints and embedded NOAA ONMS boundaries. Boundaries are geographic context only; site membership and all averages still follow NOAA's named site list. No external basemap service.
7. **Refresh and provenance:** all requested downloads and parsing must succeed before publishing new outputs. Each source file's hash, URL, and first/last dates are recorded. A later NOAA revision can change historical values. Archive a ZIP or git commit after each reviewed update if a publication needs an exact frozen version.

## Endpoint update in this version

NOAA's station map links to current `/vs_single_pixel_exp/` pages. Some other NOAA pages and the original pilot still linked to `/vs_single_pixel_dev/`; the development files checked for FGB, Guam and CNMI ended in December 2025, while the corresponding experimental files were current through October 22, 2026. This version uses the map-linked experimental endpoints. Cache names now include a hash of the full URL so identical filenames at different endpoints cannot reuse an older source by mistake.

## Sources

- [Complete named-site page list](https://coralreefwatch.noaa.gov/product/vs/map.php)
- [Flower Garden Banks named sites](https://www.coralreefwatch.noaa.gov/product/vs_single_pixel_exp/fgb.php)
- [USVI named sites](https://www.coralreefwatch.noaa.gov/product/vs_single_pixel_exp/usvi.php)
- [NOAA product methods and heat stress levels](https://coralreefwatch.noaa.gov/product/5km/methodology.php)

NOAA labels these site products experimental; some pages are under development. The inventory and source freshness should be reviewed before operational publication.

## Viewer update — October 26, 2026

The date controls now select both the first and last month. Region changes reset the range; site/measure changes retain it where the data coverage allows. The foreground 4 DHW reference styling is retained. Only the viewer HTML/template and documentation changed in this update; the named-site source data and numerical outputs are unchanged. Future `pull_sites.py` runs retain the controls through `viewer_template.html`.

## ONMS boundaries and selectable pixels — October 27, 2026

Purple outlines show NOAA ONMS boundaries intersecting the station map extent. Station markers are now the **actual 0.05° × 0.05° footprints**, with no center dots. Their apparent width/height follows the latitude-adjusted projection; they are not arbitrary fixed-size screen symbols. Click a cell or select a station from the list/menu. Orange marks the selected cell. Regions without nearby ONMS boundaries explicitly say so. Boundary overlays do not filter stations or change any SST, anomaly or DHW calculations.

`onms_boundaries.json` embeds all 18 features from NOAA's [ONMS boundary layer](https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services/NMS_Boundaries_02032022/FeatureServer/0), retrieved October 27, 2026. Layer name: `NMS_Bndy_Update_02062026`. Display geometries were requested with `where=1=1`, `outFields=NMS_Name,NMS_Abbrv`, `returnGeometry=true`, `outSR=4326`, `maxAllowableOffset=0.001`, `geometryPrecision=5`, `f=json`; rings, names and abbreviations are retained. This generalized snapshot is for display, not spatial analysis. Ring continuity is preserved across the antimeridian and rendering is clipped to the local map frame.

Future `pull_sites.py` runs embed this saved boundary file automatically. The viewer still opens offline without map tiles or API requests. Boundary refresh is separate from SST refresh: retrieve the same layer query, validate all returned features and replace the snapshot when NOAA updates its boundaries.
