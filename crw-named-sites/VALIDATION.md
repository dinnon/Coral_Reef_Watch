# Validation — October 23, 2026

- Live NOAA pull completed: 218 sites, 218 distinct coordinates, nine groups, 12 source pages.
- All site histories start January 1, 1985 and end October 22, 2026. All groups have 501 complete monthly SST values; partial October is excluded.
- Switching the FGB, Guam and CNMI endpoints retained exactly the same site IDs and coordinates.
- Independently recomputed January 1985 and September 2026 SST means from the daily CSVs for all 218 sites, then checked all nine group means.
- Five unit tests passed: discovery filtering/deduplication, non-ASCII metadata and missing values, complete leap months, missing days, and equal pixel weighting/full coverage.
- Offline rebuild reproduced all nine region datasets exactly from the bundled source cache.
- Executed the viewer JavaScript against a DOM harness: all nine menus/maps, all 218 sites and nine group means, and all three measures (681 chart states). This is a functional test, not a browser layout inspection. The viewer template was unchanged.

Run `python test_pipeline.py` for the included unit tests; `python pull_sites.py --offline` rebuilds the bundled snapshot without network access.
