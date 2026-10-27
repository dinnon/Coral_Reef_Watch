#!/usr/bin/env python3
"""Fast FKNMS historical backfill: 5-year raster subsets, resumable quarter checkpoints.

Requires scipy (`python -m pip install scipy`). Reuses the full-boundary cell
inventory and checkpoint format of run_sst.py. Run `python backfill_netcdf.py`.
"""
from __future__ import annotations
import calendar
import csv
import datetime as dt
import io
import json
import math
from pathlib import Path
import urllib.parse
from scipy.io import netcdf_file
import run_sst as core

FIRST_YEAR = 1985
LAST_COMPLETE_YEAR = dt.datetime.now(dt.timezone.utc).year - 1


def quarter_paths(year: int, quarter: int, tile: int) -> tuple[Path, Path]:
    pixel = core.CHUNKS / f'FKNMS_{year}_q{quarter}_lat{tile:03d}.csv'
    return pixel, pixel.with_suffix('.months.json')


def block_years():
    # Aligned groups, newest first. Current-year quarters stay on the smaller CSV update path.
    end = LAST_COMPLETE_YEAR
    while end >= FIRST_YEAR:
        start = max(FIRST_YEAR, end - 4)
        yield start, end
        end = start - 1


def netcdf_request(stations: list[dict], start: int, end: int, alternate=False):
    first = f'{start}-01-31T12:00:00Z'
    last = f'{end}-12-31T12:00:00Z'
    north = max(float(s['latitude']) for s in stations)
    south = min(float(s['latitude']) for s in stations)
    selected = {(round(float(s['latitude']), 3), round(float(s['longitude']) % 360, 3)):s for s in stations}
    endpoint = (core.BACKUP_ERDDAP if alternate else core.ERDDAP).replace('.csv', '.nc')
    source = 'NOAA_DHW_monthly' if alternate else 'CRW_sst_v3_1_monthly'
    data = {}
    months = set()
    for west,east in core.regions(stations, alternate):
        constraint=(f'sea_surface_temperature[({first}):1:({last})]'
                    f'[({north}):1:({south})][({west}):1:({east})]')
        url=endpoint+'?'+urllib.parse.quote(constraint,safe='[]():-.,')
        blob=core.get(url,retries=2,timeout=90)
        nc=netcdf_file(io.BytesIO(blob),mmap=False)
        try:
            axes={name:nc.variables[name].data.copy() for name in ('time','latitude','longitude')}
            grid=nc.variables['sea_surface_temperature'].data.copy()
        finally:
            nc.close()
        for ti,t in enumerate(axes['time']):
            month=dt.datetime.fromtimestamp(float(t),dt.timezone.utc).strftime('%Y-%m')
            months.add(month)
            for yi,lat in enumerate(axes['latitude']):
                lat=round(float(lat),3)
                for xi,lon in enumerate(axes['longitude']):
                    lon=round(float(lon)%360,3)
                    station=selected.get((lat,lon))
                    if station is None:continue
                    value=float(grid[ti,yi,xi])
                    if not math.isfinite(value) or not -2<=value<=50:continue
                    data[month,station['station_id']]={'month':month,'sanctuary':'FKNMS',
                        'station_id':station['station_id'],'latitude':station['latitude'],
                        'longitude':station['longitude'],'sst_c':round(value,4),
                        'source_dataset':source+' / sea_surface_temperature'}
    expected={f'{year}-{month:02d}' for year in range(start,end+1) for month in range(1,13)}
    if not expected.issubset(months):
        raise RuntimeError(f'Missing months in NetCDF subset: {sorted(expected-months)}')
    return data,months


def main():
    boundaries=core.boundary_data()
    stations,audit=core.lattice_stations(boundaries)
    digest=core.station_hash(stations)
    core.CHUNKS.mkdir(parents=True,exist_ok=True)
    selection=core.CHUNKS/'selection.json'
    if not selection.exists() or json.loads(selection.read_text()).get('station_hash')!=digest:
        raise RuntimeError('Selection hash mismatch. Run run_sst.py --plan-only and inspect checkpoints first.')
    tiles=core.latitude_tiles(stations)
    quarter_files={}
    current=dt.datetime.now(dt.timezone.utc).year
    for year in range(FIRST_YEAR,current+1):
        for quarter,_,_,_ in core.quarter_windows(year,current):
            quarter_files[year,quarter]=[quarter_paths(year,quarter,tile)[1] for tile,_ in tiles]
    for first,last in block_years():
        print(f'Years {first}–{last}: checking raster blocks',flush=True)
        for tile,part in tiles:
            needed=[(year,quarter) for year in range(first,last+1) for quarter in range(1,5)
                    if not all(p.exists() for p in quarter_paths(year,quarter,tile))]
            if not needed:continue
            print(f'  latitude band {tile}: {len(part)} selected cells, {len(needed)} quarters to fill',flush=True)
            errors=[]
            for alternate in (False,True):
                try:
                    data,months=netcdf_request(part,first,last,alternate)
                    break
                except Exception as exc:
                    errors.append(str(exc));print(f'    endpoint failed: {exc}',flush=True)
            else:
                raise RuntimeError(f'NetCDF block {first}–{last} failed: {errors}. Rerun to resume.')
            for year,quarter in needed:
                pixel,meta=quarter_paths(year,quarter,tile)
                selected_months={f'{year}-{number:02d}' for number in range(quarter*3-2,quarter*3+1)}
                rows=[row for (month,_),row in sorted(data.items()) if month in selected_months]
                core.atomic_csv(pixel,core.PIXEL_FIELDS,rows)
                core.atomic_json(meta,{'months':sorted(selected_months & months),'station_hash':digest})
                print(f'    saved {year} Q{quarter}: {len(rows)} valid cell months',flush=True)
        core.publish_completed(quarter_files,stations,digest,audit,boundaries,FIRST_YEAR)
    # Check the current year and all historical months before declaring the full backfill done.
    meta=json.loads((core.DATA/'run_metadata.json').read_text())
    print(f"Published {meta['published_months']} months; full history: {meta['complete_history']}",flush=True)

if __name__=='__main__':main()
