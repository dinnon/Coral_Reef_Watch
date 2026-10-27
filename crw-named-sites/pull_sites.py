#!/usr/bin/env python3
"""Download NOAA named 5 km reef sites; build monthly CSVs and a standalone viewer."""
import argparse
import calendar
import csv
import hashlib
import io
import json
import math
import re
import shutil
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
METRICS = {'sst_c': 'SST', 'ssta_c': 'SSTA', 'hotspot_c': 'HS', 'dhw_c_weeks': 'DHW'}
MONTH_METRICS = ['sst_c', 'ssta_c', 'peak_dhw_c_weeks']

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls = []
    def handle_starttag(self, tag, attrs):
        url = dict(attrs).get('href', '')
        if tag == 'a' and urlparse(url).path.endswith('.txt'):
            self.urls.append(url)

def fetch(url):
    req = Request(url, headers={'User-Agent': 'SanctuaryWatch named-site pilot/2.0'})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=60) as response:
                return response.read().decode('utf-8-sig')
        except (URLError, TimeoutError) as exc:
            if attempt == 2 or (isinstance(exc, HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504)):
                raise RuntimeError(f'Could not download {url}: {exc}') from exc
            time.sleep(2 ** attempt)

def discover_sites(text, page):
    links = Links(); links.feed(text)
    return sorted({urljoin(page, link) for link in links.urls
                   if urlparse(urljoin(page, link)).hostname in ('coralreefwatch.noaa.gov', 'www.coralreefwatch.noaa.gov')
                   and '/data/' in urlparse(urljoin(page, link)).path
                   and '/vs_single_pixel' in urlparse(urljoin(page, link)).path})

def cached_text(url, local, offline=False, cache_hours=0):
    if offline or (local.exists() and cache_hours > 0 and time.time() - local.stat().st_mtime < cache_hours * 3600):
        return local.read_text(encoding='utf-8')
    text = fetch(url)
    # A failed transfer never replaces the previous complete cache file.
    tmp = local.with_suffix(local.suffix + '.tmp')
    tmp.write_text(text, encoding='utf-8'); tmp.replace(local)
    return text

def parse_site(text, url, region):
    lines = text.splitlines()
    def metadata(label):
        for i, line in enumerate(lines):
            if line.strip().startswith(label):
                return next(x.strip() for x in lines[i+1:] if x.strip())
        raise ValueError(f'Missing {label} in {url}')
    meta = {'id': Path(urlparse(url).path).stem, 'region': region,
            'name': metadata('Name:'), 'lat': float(metadata('Latitude:')),
            'lon': float(metadata('Longitude:')), 'mmm_c': float(metadata('Maximum Monthly Mean')),
            'source_url': url}
    if not (-90 <= meta['lat'] <= 90 and -180 <= meta['lon'] <= 180):
        raise ValueError('Invalid coordinates')
    header_index = next((i for i, line in enumerate(lines) if line.strip().startswith('YYYY,')), None)
    if header_index is None:
        raise ValueError(f'Unrecognized site format: {url}')
    reader = csv.DictReader(io.StringIO('\n'.join(lines[header_index:])), skipinitialspace=True)
    required = {'YYYY', 'MM', 'DD', 'SST', 'SSTA', 'HS', 'DHW'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Missing daily fields')
    daily = []
    previous = None
    for raw in reader:
        d = date(int(raw['YYYY']), int(raw['MM']), int(raw['DD']))
        if previous and d <= previous:
            raise ValueError(f'Duplicate/unordered date {d} at {meta["name"]}')
        previous = d
        row = {'date': d.isoformat()}
        for target, source in METRICS.items():
            value = float(raw[source])
            row[target] = None if not math.isfinite(value) or value <= -900 else value
        if row['sst_c'] is not None and not -5 <= row['sst_c'] <= 45:
            raise ValueError(f'Unexpected SST on {d}')
        if row['dhw_c_weeks'] is not None and row['dhw_c_weeks'] < 0:
            raise ValueError(f'Unexpected DHW on {d}')
        daily.append(row)
    if not daily:
        raise ValueError('Empty time series')
    meta.update(first_date=daily[0]['date'], last_date=daily[-1]['date'], days_reported=len(daily),
                source_sha256=hashlib.sha256(text.encode()).hexdigest())
    return meta, daily

def summarize(daily):
    by_month = defaultdict(list)
    for row in daily:
        by_month[row['date'][:7]].append(row)
    output = []
    for month, rows in sorted(by_month.items()):
        year, number = map(int, month.split('-'))
        expected = calendar.monthrange(year, number)[1]
        r = {'month': month, 'days_reported': len(rows), 'days_expected': expected}
        for target, source in [('sst_c', 'sst_c'), ('ssta_c', 'ssta_c'), ('peak_dhw_c_weeks', 'dhw_c_weeks')]:
            values = [x[source] for x in rows if x[source] is not None]
            r['valid_days_' + target] = len(values)
            r[target] = round((max(values) if target.startswith('peak_') else sum(values)/len(values)), 4) if len(values) == expected else None
        output.append(r)
    return output

def region_summary(stations):
    # Equal weights per distinct grid cell; multiple site aliases cannot double its weight.
    unique = {}
    for station in sorted(stations, key=lambda s: s['id']):
        key = (round(station['lat'], 6), round(station['lon'], 6))
        if key not in unique:
            unique[key] = station
        station['average_member'] = unique[key]['id'] == station['id']
    members = list(unique.values())
    indexed = {s['id']: {r['month']: r for r in s['monthly']} for s in members}
    months = sorted({m for rows in indexed.values() for m in rows})
    result = []
    for month in months:
        row = {'month': month, 'n_expected': len(members)}
        for metric in MONTH_METRICS:
            values = [indexed[s['id']].get(month, {}).get(metric) for s in members]
            valid = [v for v in values if v is not None]
            row['n_' + metric] = len(valid)
            complete = len(valid) == len(members)
            row[metric] = round(sum(valid)/len(valid), 4) if complete else None
            row['min_' + metric] = min(valid) if complete else None
            row['max_' + metric] = max(valid) if complete else None
        result.append(row)
    return result

def write_csv(path, rows, columns=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not columns:
        columns = list(rows[0])
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regions', nargs='+', help='Region ids from regions.json; default: all configured')
    parser.add_argument('--offline', action='store_true', help='Rebuild from previously downloaded raw cache')
    parser.add_argument('--workers', type=int, default=4, help='Concurrent site downloads (1–8; default: 4)')
    parser.add_argument('--cache-hours', type=float, default=0, help='Reuse source files downloaded within this many hours; default 0 refreshes everything')
    parser.add_argument('--list-regions', action='store_true', help='List configured groups and exit')
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or args.cache_hours < 0:
        parser.error('--workers must be 1–8 and --cache-hours must be nonnegative')
    config = json.loads((ROOT/'regions.json').read_text(encoding='utf-8'))
    if args.list_regions:
        for key, region in config.items(): print(f'{key}: {region["name"]}')
        return
    selected = args.regions or list(config)
    for key in selected:
        if key not in config:
            parser.error(f'Unknown region {key}; choose from {list(config)}')
    cache = ROOT/'cache'; cache.mkdir(exist_ok=True)
    all_regions = []
    with tempfile.TemporaryDirectory(prefix='build-', dir=ROOT) as tmp:
        stage = Path(tmp)
        for rid in selected:
            region = {'id': rid, 'name': config[rid]['name'], 'pages': config[rid]['pages'], 'stations': []}
            urls = set()
            for page in config[rid]['pages']:
                key = hashlib.sha256(page.encode()).hexdigest()[:16] + '.html'
                local = cache/key
                text = cached_text(page, local, args.offline, args.cache_hours)
                page_urls = discover_sites(text, page)
                if not page_urls:
                    raise ValueError(f'No single-pixel data links found on {page}; outputs were not updated')
                urls.update(page_urls)
            if not urls:
                raise ValueError(f'No single-pixel data links found for {rid}')
            print(f'{region["name"]}: found {len(urls)} site files', flush=True)
            def process_site(url):
                sid = Path(urlparse(url).path).stem
                # Key by the full source URL: NOAA can publish the same basename
                # in both development and current experimental directories.
                local = cache/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.txt')
                text = cached_text(url, local, args.offline, args.cache_hours)
                meta, daily = parse_site(text, url, rid)
                meta['monthly'] = summarize(daily)
                write_csv(stage/rid/'daily'/f'{sid}.csv', daily)
                return meta
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for i, meta in enumerate(pool.map(process_site, sorted(urls)), 1):
                    region['stations'].append(meta)
                    print(f'  {i}/{len(urls)} {meta["name"]} through {meta["last_date"]}', flush=True)
            region['monthly'] = region_summary(region['stations'])
            region['unique_pixels'] = sum(s['average_member'] for s in region['stations'])
            write_csv(stage/rid/'stations.csv', [{k:v for k,v in s.items() if k!='monthly'} for s in region['stations']])
            write_csv(stage/rid/'station_monthly.csv', [dict(station_id=s['id'], station_name=s['name'], **r) for s in region['stations'] for r in s['monthly']])
            write_csv(stage/rid/'region_monthly.csv', region['monthly'])
            all_regions.append(region)
        coverage = []
        for region in all_regions:
            complete = [r['month'] for r in region['monthly'] if r['sst_c'] is not None]
            coverage.append(dict(region=region['id'], name=region['name'], sites=len(region['stations']),
                                 unique_pixels=region['unique_pixels'],
                                 first_date=min(s['first_date'] for s in region['stations']),
                                 earliest_source_end=min(s['last_date'] for s in region['stations']),
                                 latest_source_end=max(s['last_date'] for s in region['stations']),
                                 first_complete_sst_month=complete[0] if complete else '',
                                 last_complete_sst_month=complete[-1] if complete else ''))
        write_csv(stage/'coverage.csv', coverage)
        bundle = {'schema_version': 1, 'built_utc': datetime.now(timezone.utc).isoformat(),
                  'build_mode': 'cached sources' if args.offline else 'NOAA download with recent cache' if args.cache_hours else 'NOAA download', 'regions': all_regions}
        serialized = json.dumps(bundle, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        (stage/'viewer_data.json').write_text(serialized, encoding='utf-8')
        template = (ROOT/'viewer_template.html').read_text(encoding='utf-8')
        rendered = template.replace('__BUNDLE_JSON__', serialized.replace('</', '<\\/'))
        # Publish only after all requested sites and outputs validate. Keep prior data on fetch/parse failure.
        dest = ROOT/'data'
        dest.mkdir(exist_ok=True)
        for child in stage.iterdir():
            target = dest/child.name
            if child.is_dir():
                if target.exists(): shutil.rmtree(target)
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
        (ROOT/'index.html.tmp').write_text(rendered, encoding='utf-8')
        (ROOT/'index.html.tmp').replace(ROOT/'index.html')
        print(f'Built {len(all_regions)} regions. Open {ROOT/"index.html"}', flush=True)

if __name__ == '__main__':
    main()
