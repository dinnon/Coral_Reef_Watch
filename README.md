# Green SST / red DHW regional figures

## Open a simple standalone figure
Each of these files includes its own data and works offline. Open it directly in a browser:
- figure-american-samoa.html — threshold 28°C
- figure-florida-keys.html — threshold unset
- figure-flower-garden-banks.html — threshold unset
- figure-northwestern-hawaiian-islands.html — threshold unset
- figure-main-hawaiian-islands.html — threshold unset

## Edit an individual figure
Open that HTML in a plain-text/code editor. Near the top, find FIGURE_SETTINGS:

    bleachingThresholdC: 28,
    thresholdLabel: 'Bleaching Threshold',
    showDHW: true

Change 28 to your chosen °C value; use null to hide the line. Save and refresh the browser. No JSON, Python, or internet connection is needed for this edit. Settings in one standalone file do not change another file. These are user-specified reference thresholds, not calculated NOAA bleaching thresholds or alert levels.

## Full viewer
Open index.html for the region/measure selectors and CSV import controls. Edit SITE_THRESHOLDS near its top. Its Figure-only view link now opens the SAME HTML with ?view=figure, so it uses exactly the same threshold settings. index-figure.html is also retained as an independent generic figure viewer; edit its own SITE_THRESHOLDS if using it directly (it defaults to Florida Keys).

SST remains green; monthly peak daily DHW uses a light red line with 22% opacity fill and an independent right axis. The standalone figures start with DHW on; the checkbox toggles it. Historical El Niño shading and date controls remain. Missing/incomplete months are omitted. Data and ENSO snapshots have not been recalculated or refreshed. Station footprints are not ONMS-wide averages. Data refreshes still use the existing data workflow; imported CSVs apply to the current session.

Threshold reference lines use 50% opacity and a thinner dashed stroke, with no white backing, so overlapping data remain visible.

## DHW alert-level references
Both the DHW-only chart and the SST/DHW overlay show AL1–AL5 references at 4, 8, 12, 16, and 20°C-weeks. The DHW axis includes all five thresholds. These are reference lines for monthly peak DHW, not monthly alert classifications: daily HotSpot must also be at least 1°C. They do not calculate NOAA's 7-day maximum Bleaching Alert Area product.
