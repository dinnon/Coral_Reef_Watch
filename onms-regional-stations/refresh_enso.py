#!/usr/bin/env python3
"""Refresh the historical ONI shading snapshot; run pull_stations.py --offline afterwards."""
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

SOURCE = 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v5/'
ROOT = Path(__file__).resolve().parent


def parse_snapshot(source):
    months = []
    for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', source, re.S | re.I):
        cells = [html.unescape(re.sub('<[^>]+>', '', v)).strip()
                 for v in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', tr, re.S | re.I)]
        if not cells or not re.fullmatch(r'\d{4}', cells[0]):
            continue
        for month, value in enumerate(cells[1:13], 1):
            if re.fullmatch(r'-?\d+\.\d+', value):
                months.append({'month': f'{cells[0]}-{month:02}', 'oni': float(value)})
    if len(months) < 900:
        raise ValueError('Incomplete ONI source table; previous snapshot retained')
    indices = [int(r['month'][:4]) * 12 + int(r['month'][5:]) - 1 for r in months]
    if any(b != a + 1 for a, b in zip(indices, indices[1:])):
        raise ValueError('ONI months are missing, duplicated or out of order')
    episodes, run = [], []
    for row in months + [{'oni': -999}]:
        if row['oni'] >= .5:
            run.append(row)
        else:
            if len(run) >= 5:
                episodes.append({'start': run[0]['month'], 'end': run[-1]['month']})
            run = []
    return {'source_url': SOURCE, 'retrieved_utc': datetime.now(timezone.utc).date().isoformat(),
            'index': 'ONI (ERSSTv5)', 'source_through': months[-1]['month'],
            'method': 'ONI >= 0.5 C for at least five consecutive overlapping 3-month seasons. '
                      'Each season maps to its center month (DJF = January); start/end months inclusive. '
                      'Historical ONI context, not the operational RONI classification. '
                      'No extrapolation beyond observed qualifying seasons.',
            'episodes': episodes, 'monthly_oni': months}


if __name__ == '__main__':
    with urlopen(SOURCE, timeout=60) as response:
        snapshot = parse_snapshot(response.read().decode('utf-8'))
    path = ROOT / 'enso_periods.json'
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    print(f"Saved historical ONI through {snapshot['source_through']}; run pull_stations.py --offline to rebuild HTML.")
