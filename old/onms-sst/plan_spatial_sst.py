#!/usr/bin/env python3
"""Preview the expanded FKNMS/PNMS SST sampling cells without fetching SST.

Run in IDLE, then inspect data/stations_spatial_v2.csv and the audit JSON.
"""

import sys

from build_spatial_sst import run


if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--plan-only"]
    run()
