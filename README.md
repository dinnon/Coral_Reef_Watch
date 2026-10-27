# Viewer updates — October 27, 2026

- Regional stations: light-grey historical El Niño (ONI) bands and a standalone `onms-regional-stations/index-figure.html` containing only the figure and date controls. Open the **Figure-only view** link from the full viewer to use its selected region and measure.
- Named sites: embedded NOAA ONMS boundaries and selectable 0.05° station pixels, replacing center dots. Boundaries provide context and do not alter station membership or averages.
- Both Python refresh workflows preserve the changes. Keep the new `enso_periods.json` and `onms_boundaries.json` alongside their scripts/templates. See each folder's README for source dates, methods and refresh instructions.
- The historical ONI source snapshot ends May 2026; later unshaded months are unclassified here. The previous embedded SST/DHW snapshots are retained exactly.

# Offline viewer + date range update — October 26, 2026

Copy the files from each folder in this ZIP into the matching existing project folder, replacing files with the same name. Your existing data and cache folders are not overwritten by this update.

Regional stations: replace `index.html`, `viewer_template.html`, `pull_stations.py`, and `README.md`. The Python change automatically embeds the local monthly data after each future pull. The new template is required for rebuilding.
Named sites: replace `index.html`, `viewer_template.html`, and `README.md`.

Then double-click either `index.html`. Both viewers already include saved data and open offline without selecting CSVs. Move the two handles on the shared timeline, or enter exact From / To months. All dates resets the view. A single month is allowed. The prominent 4 DHW reference remains.

The bundled regional HTML contains source data through October 24, 2026; the named-site HTML retains the October 22, 2026 data snapshot. Complete current monthly values end September 2026. The regional Samoas source has two missing historical days, which remain gaps at monthly resolution. No missing data were filled.

If your local data are newer than these snapshots, rebuild using your existing files:

- In the regional folder: `python pull_stations.py --offline` (reads local CSVs).
- In the named-site folder: `python pull_sites.py --offline` (reads the saved NOAA cache).

No NOAA connection is used by either offline command. Normal future updates still use `python pull_stations.py` or `python pull_sites.py` respectively, and now both regenerate their embedded HTML. Hosting the HTML alone does not refresh the data.

Validation: both viewers passed functional checks for offline startup, all regions, both handles, exact month fields, one-month plots, bounds/clamping, reset and DHW foreground ordering. The regional embedded records match their CSVs; invalid CSVs do not replace the prior viewer. Named-site data and calculations are unchanged. Browser layout was not tested in a real browser.
