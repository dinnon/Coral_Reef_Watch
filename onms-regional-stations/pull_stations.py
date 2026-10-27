#!/usr/bin/env python3
"""Download NOAA CRW regional station daily series and derive monthly summaries."""

import argparse
import csv
import math
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import date, timedelta, datetime, timezone
from urllib.request import Request, urlopen

BASE = "https://coralreefwatch.noaa.gov/product/vs/data/"
ROOT = Path(__file__).resolve().parent
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
                   "mean_ssta_at_90th_hotspot_c", "max_dhw_from_90th_hotspot_c_weeks")
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
                       mean(3), mean(1), mean(2), mean(4), f"{max(row[6] for row in rows):.4f}"))
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


def build_viewer(output_dir, viewer_path):
    """Embed the available local monthly CSVs; never request data from NOAA."""
    stations = {}
    for station_id in STATIONS:
        folder = output_dir / station_id.lower()
        monthly_path = folder / 'monthly.csv'
        if not monthly_path.exists():
            continue
        with monthly_path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if not set(MONTHLY_COLUMNS[:-1]).issubset(reader.fieldnames or []):
                raise ValueError(f'Unexpected monthly columns in {monthly_path}')
            rows = list(reader)
        if not rows:
            raise ValueError(f'No monthly records in {monthly_path}')
        months = [r['month'] for r in rows]
        if months != sorted(set(months)) or any(not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', m) for m in months):
            raise ValueError(f'Invalid or unordered months in {monthly_path}')
        # Support older monthly CSVs whose DHW was supplied separately by daily.csv.
        if 'max_dhw_from_90th_hotspot_c_weeks' not in rows[0] and (folder / 'daily.csv').exists():
            peaks = {}
            with (folder / 'daily.csv').open(encoding='utf-8-sig', newline='') as stream:
                for row in csv.DictReader(stream):
                    month = row['date'][:7]
                    value = float(row['dhw_from_90th_hotspot_c_weeks'])
                    if not math.isfinite(value) or value < 0:
                        raise ValueError(f'Invalid daily DHW in {folder}')
                    peaks[month] = max(peaks.get(month, 0), value)
            for row in rows:
                row['max_dhw_from_90th_hotspot_c_weeks'] = str(peaks[row['month']]) if row['month'] in peaks else ''
        stations[station_id.lower()] = rows
    if not stations:
        raise ValueError(f'No station monthly CSVs found in {output_dir}. Run a pull first.')
    bundle = {'schema': 'crw-regional-stations-v1',
              'built_utc': datetime.now(timezone.utc).isoformat(), 'stations': stations}
    serialized = json.dumps(bundle, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    template = (ROOT / 'viewer_template.html').read_text(encoding='utf-8')
    if template.count('__BUNDLE_JSON__') != 1:
        raise ValueError('Viewer template must contain exactly one bundle placeholder')
    enso = json.loads((ROOT / 'enso_periods.json').read_text(encoding='utf-8'))
    template = template.replace('__ENSO_JSON__', json.dumps(enso, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
    rendered = template.replace('__BUNDLE_JSON__', serialized.replace('</', '<\\/'))
    html = rendered.replace('__VIEW_MODE__', 'full')
    figure_html = rendered.replace('__VIEW_MODE__', 'figure')
    output_dir.mkdir(parents=True, exist_ok=True)
    viewer_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / 'viewer_data.json'
    json_tmp = json_path.with_suffix('.json.tmp')
    json_tmp.write_text(serialized, encoding='utf-8'); json_tmp.replace(json_path)
    html_tmp = viewer_path.with_suffix('.html.tmp')
    html_tmp.write_text(html, encoding='utf-8'); html_tmp.replace(viewer_path)
    figure_path = viewer_path.with_name(viewer_path.stem + '-figure.html')
    figure_tmp = figure_path.with_suffix('.html.tmp')
    figure_tmp.write_text(figure_html, encoding='utf-8'); figure_tmp.replace(figure_path)
    print(f'Built offline-ready viewer with {len(stations)} regions: {viewer_path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stations", nargs="*", metavar="STATION",
                        help="ONMS code(s); defaults to all five")
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    parser.add_argument("--viewer", type=Path, default=ROOT / "index.html")
    parser.add_argument("--offline", action="store_true", help="Rebuild the embedded viewer from existing CSVs without downloading")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    for station_id in args.stations:
        if station_id not in STATIONS:
            parser.error(f'Unknown station {station_id}; choose from {list(STATIONS)}')
    if not args.offline:
        for station_id in args.stations or STATIONS:
            run(station_id, args.output, args.timeout)
    build_viewer(args.output, args.viewer)


if __name__ == "__main__":
    main()
