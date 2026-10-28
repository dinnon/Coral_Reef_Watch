# Named-site comparison test viewer

Open `compare.html` directly in your browser. It is self-contained and works offline. For GitHub Pages, upload it into `crw-named-sites/`, then open that folder's `compare.html` URL. The existing `index.html` is unchanged.

## Compare sites

- Choose a region. Its first two sites are selected initially; region changes reset selection and map extent.
- Click a pixel, station-list button, or Add/remove site menu option to toggle a line. Up to eight sites can be selected in the current region.
- Each selected pixel and chart line shares a stable color until that site is removed. Click a legend entry to remove it. Aliases that occupy the same pixel can be selected separately through the list/menu.
- Toggle Regional average independently. This is the original mean over **all unique named-site pixels in the region**, not a newly calculated mean of the comparison selection.
- All lines share one metric: SST, NOAA SST anomaly, or monthly peak daily DHW. Comparisons across different regions or mixed-unit axes are not part of this test.
- The two date handles, exact month inputs, hover values and CSV export work across the selected series. Export is in long format (month, series ID/name, metric, value, coverage). Missing or incomplete values remain blank.
- The DHW reference is shown only while individual site lines are selected. Regional mean DHW is descriptive; the 4 DHW reference does not classify that average or demonstrate observed bleaching.

## Map navigation

Scroll within the map to zoom around the pointer, use +/− buttons, or drag to pan. Touch users can drag and use the zoom buttons. Reset map restores all sites in the current region. When the map has keyboard focus, use +/− to zoom, arrow keys to pan, and 0 to reset. ONMS boundaries and pixel footprints scale together. No online basemap or map API is required.

## Refresh the test viewer

Copy `compare.html`, `compare_template.html`, and `build_compare.py` into the existing `crw-named-sites` folder. After your usual data refresh, run:

```bash
python build_compare.py
```

This reads existing `data/viewer_data.json` and `onms_boundaries.json` and rebuilds only `compare.html`. It downloads no data and does not modify the main viewer. Keep editing `compare_template.html` for changes that should survive a rebuild. No additional Python dependencies are needed.

## Validation

DOM-based checks passed for all nine regions: selection toggles, three measures, one-month windows, missing-value handling, empty selection, the eight-site limit, zoom/reset, keyboard and pointer panning, wheel zoom, and suppression of selection clicks after dragging. Compared plotted values directly against the source bundle and checked CSV output. SVG chart/map renders were inspected visually. Full browser layout and physical touch gestures remain to be checked during this pilot.
