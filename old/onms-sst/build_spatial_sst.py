#!/usr/bin/env python3
"""Build an expanded, fixed-grid monthly SST series for FKNMS and PNMS.

Run in IDLE or with ``python build_spatial_sst.py``. The original station and
SST CSVs are never overwritten. Completed years are checkpointed separately.
The viewer uses these new results only after every historical year succeeds.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import statistics
import urllib.parse

import update_sst as old

DATA = old.DATA
CHUNKS = DATA / "spatial_v2_chunks"
SITES = {"FKNMS": 1, "PNMS": 1}  # Every native 0.05° cell center inside the polygons.
STATION_FIELDS = old.STATION_FIELDS + ["grid_stride", "sampling_method"]
METHOD = "spatial_v2: all native-grid centers within NOAA ONMS polygons; latitude-area-weighted valid-cell mean"


def boundary_data() -> dict:
    path = DATA / "sanctuary_boundaries.geojson"
    if not path.exists():
        print("Boundary GeoJSON absent; retrieving the NOAA ONMS boundaries…", flush=True)
        old.write_boundary_geojson(old.fetch_boundary_features())
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("type") != "FeatureCollection" or not obj.get("features"):
        raise RuntimeError("Boundary GeoJSON lacks sanctuary polygons")
    return obj


def lattice_stations(boundaries: dict) -> tuple[list[dict], dict]:
    """Enumerate an aligned lattice and clip cell centers to each polygon."""
    stations: dict[tuple[str, int, int], dict] = {}
    component_counts: dict[str, list[int]] = {s: [] for s in SITES}
    for feat in boundaries["features"]:
        props = feat.get("properties") or {}
        site = props.get("sanctuary")
        if site not in SITES:
            continue
        stride = SITES[site]
        polygons = old.boundary_polygons(feat.get("geometry") or {})
        for rings in polygons:
            exterior = old.unwrap(rings[0], rings[0][0][0])
            west, east = min(p[0] for p in exterior), max(p[0] for p in exterior)
            south, north = min(p[1] for p in exterior), max(p[1] for p in exterior)
            i0 = math.ceil((west - .025) / .05 - 1e-7)
            i1 = math.floor((east - .025) / .05 + 1e-7)
            j0 = max(0, math.ceil((89.975 - north) / .05 - 1e-7))
            j1 = min(3599, math.floor((89.975 - south) / .05 + 1e-7))
            inside_count = 0
            for j in range(math.ceil(j0 / stride) * stride, j1 + 1, stride):
                lat = round(89.975 - j * .05, 3)
                for i in range(math.ceil(i0 / stride) * stride, i1 + 1, stride):
                    im = i % 7200
                    lon360 = round(.025 + im * .05, 3)
                    lon = round(lon360 if lon360 < 180 else lon360 - 360, 3)
                    if not old.in_polygon(lon, lat, rings):
                        continue
                    inside_count += 1
                    key = site, j, im
                    stations[key] = {"sanctuary": site, "station_id": f"{site}-v2-y{j}-x{im}",
                        "latitude": lat, "longitude": lon, "spatial_relation": "inside",
                        "boundary_objectid": props.get("boundary_objectid", ""),
                        "geometry_source": boundaries.get("source_url", old.BOUNDARY_URL),
                        "grid_stride": stride, "sampling_method": METHOD}
            component_counts[site].append(inside_count)
    result = [stations[k] for k in sorted(stations)]
    counts = {s: sum(r["sanctuary"] == s for r in result) for s in SITES}
    for site, count in counts.items():
        if count < 20:
            raise RuntimeError(f"Only {count} {site} cells selected; inspect boundary geometry and lattice before retrieval")
        missed = sum(n == 0 for n in component_counts[site])
        if missed:
            print(f"WARNING: {site} lattice missed {missed} small polygon components; inspect the map", flush=True)
        print(f"{site}: {count} fixed interior cells at {SITES[site] * .05:.2f}° spacing", flush=True)
    return result, {"counts": counts, "component_counts": component_counts}


def station_hash(stations: list[dict]) -> str:
    fields = [(r["station_id"], r["latitude"], r["longitude"]) for r in stations]
    return hashlib.sha256(json.dumps(fields, separators=(",", ":")).encode()).hexdigest()


def latitude_tiles(stations: list[dict]) -> list[tuple[int, list[dict]]]:
    """Limit NOAA responses and checkpoint each 20-row (about 1°) band."""
    tiles: dict[int, list[dict]] = {}
    for station in stations:
        j = int(round((89.975 - float(station["latitude"])) / .05))
        tiles.setdefault(j // 20, []).append(station)
    return sorted(tiles.items())


def regions(site_stations: list[dict], alternate: bool) -> list[tuple[float, float]]:
    if alternate:
        # CoastWatch uses signed longitude; split a date-line site into two ranges.
        groups = [[float(s["longitude"]) for s in site_stations if float(s["longitude"]) < 0],
                  [float(s["longitude"]) for s in site_stations if float(s["longitude"]) >= 0]]
        return [(min(group), max(group)) for group in groups if group]
    vals = [float(s["longitude"]) % 360 for s in site_stations]
    if max(vals) - min(vals) > 180:
        raise RuntimeError("Selected 0–360° longitudes cross zero; split the region before requesting ERDDAP")
    return [(min(vals), max(vals))]


def request_range(site_stations: list[dict], first: str, last: str, alternate: bool) -> list[dict]:
    site = site_stations[0]["sanctuary"]
    stride = int(site_stations[0]["grid_stride"])
    north = max(float(s["latitude"]) for s in site_stations)
    south = min(float(s["latitude"]) for s in site_stations)
    by_cell = {(int(round((89.975 - float(s["latitude"])) / .05)),
                int(round(((float(s["longitude"]) % 360) - .025) / .05))): s for s in site_stations}
    endpoint = old.BACKUP_ERDDAP if alternate else old.ERDDAP
    source = "NOAA_DHW_monthly" if alternate else "CRW_sst_v3_1_monthly"
    result: dict[tuple[str, str], dict] = {}
    for west, east in regions(site_stations, alternate):
        constraint = (f"sea_surface_temperature[({first}):1:({last})]"
                      f"[({north}):{stride}:({south})][({west}):{stride}:({east})]")
        url = endpoint + "?" + urllib.parse.quote(constraint, safe="[]():-.,")
        response = old.get(url, retries=1, timeout=90).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(response))
        fields = reader.fieldnames or []
        if not {"time", "latitude", "longitude", "sea_surface_temperature"}.issubset(fields):
            raise RuntimeError(f"Unexpected ERDDAP columns: {fields}")
        for row in reader:
            try:
                value = float(row["sea_surface_temperature"])
                lat = float(row["latitude"])
                lon = float(row["longitude"]) % 360
            except (ValueError, TypeError):  # Units row, land/NaN, or missing value.
                continue
            if not math.isfinite(value) or not -2 <= value <= 50:
                continue
            cell = (int(round((89.975 - lat) / .05)), int(round((lon - .025) / .05)))
            station = by_cell.get(cell)
            if not station:
                continue
            month = row["time"][:7]
            result[month, station["station_id"]] = {"month": month, "sanctuary": site,
                "station_id": station["station_id"], "latitude": station["latitude"],
                "longitude": station["longitude"], "sst_c": round(value, 4),
                "source_dataset": source + " / sea_surface_temperature"}
    return [result[k] for k in sorted(result)]


def fetch_year(site_stations: list[dict], year: int, current_year: int) -> list[dict]:
    start = f"{year}-01-31T12:00:00Z"
    stop = "last" if year == current_year else f"{year}-12-31T12:00:00Z"
    def try_servers(first: str, last: str, count: int | None) -> list[dict]:
        errors = []
        for alternate in (False, True):
            try:
                rows = request_range(site_stations, first, last, alternate)
                months = {r["month"] for r in rows}
                if count is not None and len(months) != count:
                    raise RuntimeError(f"Only {len(months)} of {count} months returned")
                if not rows:
                    raise RuntimeError("No valid cells returned")
                return rows
            except RuntimeError as e:
                errors.append(str(e))
                print(f"  {('Alternate' if alternate else 'Primary')} server failed: {e}", flush=True)
        raise RuntimeError(" | ".join(errors))

    try:
        return try_servers(start, stop, None if year == current_year else 12)
    except RuntimeError as whole_year_error:
        if year == current_year:
            raise RuntimeError(f"{site_stations[0]['sanctuary']} {year}: {whole_year_error}") from whole_year_error
        print(f"  Retrying {year} in three-month blocks…", flush=True)
    combined = []
    for first_month in (1, 4, 7, 10):
        last_month = first_month + 2
        first_day = calendar.monthrange(year, first_month)[1]
        last_day = calendar.monthrange(year, last_month)[1]
        first = f"{year}-{first_month:02d}-{first_day:02d}T12:00:00Z"
        last = f"{year}-{last_month:02d}-{last_day:02d}T12:00:00Z"
        combined.extend(try_servers(first, last, 3))
    return combined


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    old.atomic_csv(path, fields, rows)


def aggregate_spatial(pixel_files: list[Path], stations: list[dict]) -> list[dict]:
    """Read checkpoint files one row at a time, keeping only monthly statistics."""
    expected = {site: sum(s["sanctuary"] == site for s in stations) for site in SITES}
    groups: dict[tuple[str, str], dict] = {}
    for path in pixel_files:
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                value = float(row["sst_c"])
                weight = math.cos(math.radians(float(row["latitude"])))
                group = groups.setdefault((row["month"], row["sanctuary"]),
                    {"weighted": 0., "weight": 0., "min": value, "max": value, "n": 0})
                group["weighted"] += value * weight
                group["weight"] += weight
                group["min"] = min(group["min"], value)
                group["max"] = max(group["max"], value)
                group["n"] += 1
    means = {key: group["weighted"] / group["weight"] for key, group in groups.items()}
    baseline = {}
    for site in SITES:
        for calendar_month in range(1, 13):
            vals = [mean for (month, code), mean in means.items() if code == site
                    and 1991 <= int(month[:4]) <= 2020 and int(month[5:]) == calendar_month]
            if len(vals) >= 20:
                baseline[site, calendar_month] = statistics.mean(vals)
    summary = []
    for (month, site), group in sorted(groups.items()):
        mean = means[month, site]
        reference = baseline.get((site, int(month[5:])))
        summary.append({"month": month, "sanctuary": site, "mean_sst_c": round(mean, 4),
            "min_sst_c": round(group["min"], 4),
            "max_sst_c": round(group["max"], 4),
            "n_valid": group["n"], "n_stations": expected[site],
            "coverage_pct": round(100 * group["n"] / expected[site], 1),
            "anomaly_c": round(mean - reference, 4) if reference is not None else "",
            "source_dataset": old.SOURCE,
            "spatial_method": METHOD + " (0.05 degree grid)"})
    return summary


def run() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start-year", type=int, default=1985)
    ap.add_argument("--plan-only", action="store_true", help="Write proposed cells and coverage audit without SST requests")
    args = ap.parse_args()
    boundaries = boundary_data()
    stations, audit = lattice_stations(boundaries)
    digest = station_hash(stations)
    CHUNKS.mkdir(parents=True, exist_ok=True)
    state_path = CHUNKS / "selection.json"
    if state_path.exists():
        prior = json.loads(state_path.read_text(encoding="utf-8"))
        if prior.get("station_hash") != digest:
            if any(CHUNKS.glob("*.csv")):
                raise RuntimeError("Boundary or sampling locations changed. Preserve the existing spatial_v2_chunks folder and move it aside before a fresh backfill.")
            state_path.unlink()  # A plan with no SST chunks can be safely revised.
    if not state_path.exists():
        old.atomic_json(state_path, {"station_hash": digest, "grid_strides": SITES,
            "boundary_retrieved_utc": boundaries.get("retrieved_utc"), "audit": audit})
    write_csv(DATA / "stations_spatial_v2.csv", STATION_FIELDS, stations)
    old.atomic_json(DATA / "spatial_v2_sampling_audit.json", {"station_counts": audit["counts"],
        "component_counts": audit["component_counts"], "grid_strides": SITES,
        "grid_spacing_degrees": {site: stride * .05 for site, stride in SITES.items()},
        "station_hash": digest, "boundary_retrieved_utc": boundaries.get("retrieved_utc"),
        "method": METHOD, "note": "All native 0.05 degree cell centers inside polygons; boundary-edge partial cells and coral habitat are not separately counted."})
    if args.plan_only:
        print("Sampling plan saved. No SST was requested. Inspect stations_spatial_v2.csv and spatial_v2_sampling_audit.json.")
        return
    this_year = dt.datetime.now(dt.timezone.utc).year
    pixel_files = []
    for site in SITES:
        selected = [r for r in stations if r["sanctuary"] == site]
        for year in range(this_year, args.start_year - 1, -1):
            for tile, tile_stations in latitude_tiles(selected):
                path = CHUNKS / f"{site}_{year}_lat{tile:03d}.csv"
                pixel_files.append(path)
                if path.exists() and year != this_year:
                    continue
                print(f"{site} {year} latitude band {tile}: retrieving {len(tile_stations)} cells…", flush=True)
                rows = fetch_year(tile_stations, year, this_year)
                if path.exists() and year == this_year:
                    with path.open(newline="", encoding="utf-8") as f:
                        prior_months = {r["month"] for r in csv.DictReader(f)}
                    new_months = {r["month"] for r in rows}
                    if not prior_months.issubset(new_months):
                        raise RuntimeError(f"{site} current-year response lost previously saved months; {path} was preserved")
                write_csv(path, old.PIXEL_FIELDS, rows)
                print(f"  Saved {len(rows)} observations from {len({r['month'] for r in rows})} months", flush=True)
    if any(not path.exists() for path in pixel_files):
        raise RuntimeError("Incomplete tile checkpoints; published outputs were not replaced")
    summary = aggregate_spatial(pixel_files, stations)
    old.atomic_json(CHUNKS / "index.json", {"station_hash": digest,
        "pixel_chunks": [p.name for p in pixel_files], "note": "Each CSV contains valid cell observations for one year and latitude band."})
    write_csv(DATA / "sst_monthly_spatial_v2.csv", old.MONTH_FIELDS, summary)
    old.atomic_json(DATA / "run_metadata_spatial_v2.json", {"updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "station_hash": digest, "boundary_retrieved_utc": boundaries.get("retrieved_utc"),
        "source": old.ERDDAP, "start_year": args.start_year, "last_month": summary[-1]["month"],
        "station_counts": audit["counts"], "component_counts": audit["component_counts"],
        "method": METHOD, "pixel_chunks_manifest": "spatial_v2_chunks/index.json",
        "complete_history": args.start_year == 1985})
    print(f"Expanded series complete: {len(summary)} sanctuary-month rows. The original CSV is unchanged.")


if __name__ == "__main__":
    run()
