#!/usr/bin/env python3
"""Export the ONMS source polygons for the SST viewer; no SST download.

Run this file in IDLE or another Python IDE. It writes
data/sanctuary_boundaries.geojson beside the existing station and SST CSVs.
"""

from update_sst import fetch_boundary_features, write_boundary_geojson


if __name__ == "__main__":
    write_boundary_geojson(fetch_boundary_features())
