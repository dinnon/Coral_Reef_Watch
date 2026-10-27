#!/usr/bin/env python3
"""Refresh the offline HTML snapshot after replacing data/sst_monthly.csv."""
import csv
import json
from pathlib import Path

root = Path(__file__).resolve().parent
with (root / 'data' / 'sst_monthly.csv').open(newline='', encoding='utf-8') as stream:
    records = [r for r in csv.DictReader(stream) if r.get('sanctuary') == 'FKNMS']
if not records:
    raise SystemExit('No FKNMS rows in data/sst_monthly.csv')
columns = ('month', 'sanctuary', 'mean_sst_c', 'p10_sst_c', 'p90_sst_c', 'n_valid', 'n_stations', 'anomaly_c')
if any(not all(k in r for k in columns) for r in records):
    raise SystemExit('Monthly CSV is missing required chart columns')
encoded = json.dumps([{k: r[k] for k in columns} for r in records], separators=(',', ':')).replace('<', '\\u003c')
page = root / 'figure_only.html'
html = page.read_text(encoding='utf-8')
start = '<script type="application/json" id="embedded-data">'
end = '</script>'
if html.count(start) != 1:
    raise SystemExit('Expected exactly one embedded-data script in figure_only.html')
left, rest = html.split(start, 1)
_, right = rest.split(end, 1)
page.write_text(left + start + encoded + end + right, encoding='utf-8')
print(f'Embedded {len(records)} FKNMS months in {page.name}')
