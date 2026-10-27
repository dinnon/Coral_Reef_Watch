#!/usr/bin/env python3
"""Download NOAA CRW regional station daily series and derive monthly summaries."""

import argparse
import csv
import math
import os
from pathlib import Path
import re
import tempfile
from datetime import date, timedelta
from urllib.request import Request, urlopen

BASE = "https://coralreefwatch.noaa.gov/product/vs/data/"
STATIONS = {
    "FKNMS": ("Florida Keys", "florida_keys.txt"),
    "FGBNMS": ("Flower Garden Banks, Texas", "flower_garden.txt"),
    "NMSAS": ("Samoas", "samoas.txt"),
    "PNMS": ("Northwestern Hawaiian Islands", "nwhi.txt"),
    "HIHWNMS": ("Main Hawaiian Islands", "hawaii.txt"),
}
DAILY_COLUMNS = ("date", "sst_min_c", "sst_max_c", "sst_at_90th_hotspot_c",
                 "ssta_at_90th_hotspot_c", "hotspot_90th_c", "dhw_from_90th_hotspot_c_weeks",
                 "baa_7day_max")
MONTHLY_COLUMNS = ("month", "days_reported", "days_in_month", "complete_month",
                   "mean_sst_at_90th_hotspot_c", "mean_sst_min_c", "mean_sst_max_c",
                   "mean_ssta_at_90th_hotspot_c")
ROW = re.compile(r"^\s*(\d{4})\s+(\d{1,2})\s+(\d{1,2})\s+(.+?)\s*$")


def parse_station(source, expected_name):
    match = re.search(r"(?m)^Name:\s*\r?\n([^\r\n]+)", source)
    if not match or match.group(1).strip() != expected_name:
        raise ValueError(f"Station identity mismatch: expected {expected_name!r}")
    if "SST@90th_HS" not in source or "SST_MIN" not in source:
        raise ValueError("Unrecognized NOAA time-series header")
    rows = []
    for line in source.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        day = date(*(int(m.group(i)) for i in (1, 2, 3)))
        values = m.group(4).split()
        if len(values) != 7:
            raise ValueError(f"Unexpected field count on {day}: {len(values)}")
        numbers = [float(v) for v in values[:6]]
        if not all(math.isfinite(v) and -100 < v < 100 for v in numbers[:5]):
            raise ValueError(f"Invalid SST or HotSpot on {day}")
        if not math.isfinite(numbers[5]) or numbers[5] < 0:
            raise ValueError(f"Invalid DHW on {day}")
        baa = int(values[6])
        if baa < 0:
            raise ValueError(f"Invalid alert level on {day}")
        rows.append((day.isoformat(), *numbers, baa))
    if not rows:
        raise ValueError("No daily observations")
    days = [date.fromisoformat(row[0]) for row in rows]
    if days != sorted(set(days)):
        raise ValueError("Daily dates are unordered or repeated")
    return rows


def missing_dates(daily):
    """Dates absent between NOAA's first and last observations; never fill them."""
    days = [date.fromisoformat(row[0]) for row in daily]
    return [left + timedelta(days=offset)
            for left, right in zip(days, days[1:])
            for offset in range(1, (right - left).days)]


def monthly_rows(daily):
    by_month = {}
    for row in daily:
        by_month.setdefault(row[0][:7], []).append(row)
    output = []
    for month, rows in by_month.items():
        year, number = map(int, month.split("-"))
        next_month = date(year + (number == 12), number % 12 + 1, 1)
        expected = (next_month - date(year, number, 1)).days
        def mean(index):
            return f"{sum(row[index] for row in rows) / len(rows):.4f}"
        output.append((month, len(rows), expected, int(len(rows) == expected),
                       mean(3), mean(1), mean(2), mean(4)))
    return output


def atomic_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent,
                                     prefix=".tmp-", delete=False) as stream:
        temporary = Path(stream.name)
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)
    os.replace(temporary, path)


def run(station_id, output_dir, timeout):
    name, filename = STATIONS[station_id]
    url = BASE + filename
    request = Request(url, headers={"User-Agent": "SanctuaryWatch regional-station pilot/1.0"})
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8-sig")
    daily = parse_station(body, name)
    monthly = monthly_rows(daily)
    gaps = missing_dates(daily)
    folder = output_dir / station_id.lower()
    # Parse and validate both tables before publishing either file.
    atomic_csv(folder / "daily.csv", DAILY_COLUMNS, daily)
    atomic_csv(folder / "monthly.csv", MONTHLY_COLUMNS, monthly)
    print(f"{station_id}: {len(daily)} daily rows through {daily[-1][0]}; "
          f"{len(monthly)} monthly rows ({sum(row[3] for row in monthly)} complete); {url}")
    if gaps:
        examples = ", ".join(day.isoformat() for day in gaps[:5])
        print(f"  NOAA source omits {len(gaps)} date(s) between first and last "
              f"observation (first: {examples}). Affected months have complete_month=0.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stations", nargs="*", choices=STATIONS, metavar="STATION",
                        help="ONMS code(s); defaults to all five")
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    for station_id in args.stations or STATIONS:
        run(station_id, args.output, args.timeout)


if __name__ == "__main__":
    main()
