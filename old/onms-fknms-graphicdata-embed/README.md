# FKNMS SST: Graphic Data modal figure

A compact, figure-only version of the existing FKNMS CoralTemp chart. It is designed for the **Code** figure type in the [Graphic Data WordPress plugin](https://github.com/ioos/sanctuarywatch_graphicdata). Graphic Data supplies the modal, tab, figure title, captions, and source/data links. This iframe supplies only the chart, two controls, a data-through status, and the CSV download.

## What is included

- `figure_only.html`: responsive standalone chart with an embedded SST snapshot, so double-clicking the file displays the chart even without a local server.
- `data/sst_monthly.csv`: the same NOAA-derived FKNMS sanctuary-wide monthly summary as the full viewer, currently January 1985–August 2026. **This is a complete historical snapshot through August 2026**; uploading this package does not schedule updates.
- `graphic_data_code_snippet.html`: iframe example; replace its placeholder GitHub Pages URL after publishing.
- `refresh_embedded_snapshot.py`: rebuilds the inline fallback in the HTML from a newer monthly CSV.

The chart displays the cosine(latitude)-weighted mean of all valid CoralTemp 0.05° grid cells whose centers lie inside the detailed FKNMS boundary, plus the unweighted 10th–90th percentile across valid cell values. The selection contains 416 cells and the included months have 414 valid SST values. The anomaly option uses the completed 1991–2020 same-calendar-month baseline.

## Place in Graphic Data

1. Host `figure_only.html` and `data/sst_monthly.csv` together on a public HTTPS static host, such as GitHub Pages. Preserve the relative `data/` path. Preview the hosted chart URL directly first.
2. Create or edit the FKNMS Scene and Modal, and add a Figure in the appropriate tab. Use **Figure Type → Code**, then paste the iframe from `graphic_data_code_snippet.html` into the **HTML/JavaScript Code** field. In the current plugin, only administrators can edit raw Code figures.
3. Set the Figure Title, short/extended captions, NOAA monitoring-program link, and a Data Link to the hosted CSV in Graphic Data. Preview in its actual modal on desktop and mobile, then publish if approved. Do not paste the full HTML document into the Code field.

The Graphic Data code renderer wraps the snippet in a white, padded content area and gives it a minimum height. The iframe has a fixed height of 460px as a practical initial size; adjust it after previewing the modal. The hosted figure URL and CSV can be replaced independently of the WordPress Figure record as long as their addresses stay stable.

## Suggested Graphic Data fields

- **Figure title:** Sanctuary-wide sea surface temperature
- **Short caption:** Monthly sea surface temperature across CoralTemp grid cells within Florida Keys National Marine Sanctuary. The shaded range shows variation among cells; source: NOAA Coral Reef Watch.
- **Extended caption:** Monthly mean SST is weighted by cosine of latitude across valid native 0.05° cells with centers inside the detailed ONMS FKNMS boundary. The shaded band spans the 10th–90th percentile of valid cell values. Coverage shows valid cells out of 416 selected cells. Satellite sea surface temperature does not measure reef-depth temperature or bleaching heat stress. The anomaly series uses the 1991–2020 mean of each calendar month using the completed historical series.
- **Monitoring Program Link:** NOAA Coral Reef Watch — https://coralreefwatch.noaa.gov/product/5km/index_5km_sst.php
- **Data Link:** Hosted `data/sst_monthly.csv` URL.

## Local preview and update

You can now **double-click `figure_only.html`** and see the embedded snapshot immediately. On a hosted HTTP(S) page, the figure first draws that snapshot, then checks `data/sst_monthly.csv` for a newer validated series. If the hosted CSV is unavailable, the snapshot remains visible with a status message.

For an update, replace `data/sst_monthly.csv` with a validated output from the full FKNMS pipeline and run `python refresh_embedded_snapshot.py` before publishing both files. This keeps direct local viewing and the hosted fallback current. A future GitHub Action could run these steps after the full backfill and QA rules are agreed.

Reference: [Graphic Data figure types](https://ioos.github.io/sanctuarywatch_graphicdata/figure-types/) and [Figure fields](https://ioos.github.io/sanctuarywatch_graphicdata/figures/).
