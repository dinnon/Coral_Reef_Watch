#!/usr/bin/env python3
"""Fetch ONMS sampling locations and CRW monthly SST; Python standard library only."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import os
import pathlib
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
BOUNDARY_URL = "https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services/NMS_Boundaries_02032022/FeatureServer/0/query"
ERDDAP = "https://oceanwatch.pifsc.noaa.gov/erddap/griddap/CRW_sst_v3_1_monthly.csv"
BACKUP_ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW_monthly.csv"
SITES = {
    "PNMS": "Papahanaumokuakea",
    "HIHWNMS": "Hawaiian Islands Humpback Whale",
    "NMSAS": "American Samoa",
    "FGBNMS": "Flower Garden Banks",
    "FKNMS": "Florida Keys",
}
STATION_FIELDS = ["sanctuary", "station_id", "latitude", "longitude", "spatial_relation", "boundary_objectid", "geometry_source"]
PIXEL_FIELDS = ["month", "sanctuary", "station_id", "latitude", "longitude", "sst_c", "source_dataset"]
MONTH_FIELDS = ["month", "sanctuary", "mean_sst_c", "min_sst_c", "max_sst_c", "n_valid", "n_stations", "coverage_pct", "anomaly_c", "source_dataset", "spatial_method"]
SOURCE = "NOAA Coral Reef Watch CoralTemp v3.1 monthly mean"


def get(url: str, retries: int = 3, timeout: int = 30) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ONMS-SST-Explorer/1.0 (research data processing)", "Accept": "application/json,text/csv,*/*"})
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            print(f"  Request to {urllib.parse.urlsplit(url).hostname} failed ({attempt + 1}/{retries}): {exc}", file=sys.stderr, flush=True)
            if isinstance(exc, urllib.error.HTTPError) and 400 <= exc.code < 500:
                break
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Could not reach {url.split('?')[0]}: {last}. Check internet/proxy access to NOAA, then rerun; already saved observations are retained.")


def atomic_csv(path: pathlib.Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def read_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def atomic_json(path: pathlib.Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def code_for(properties: dict) -> str | None:
    vals = [str(v or "").lower().replace("ā", "a").replace("ʻ", "").replace("ā", "a") for v in properties.values() if isinstance(v, str)]
    for code in SITES:
        if any(v.strip().upper() == code for v in properties.values() if isinstance(v, str)):
            return code
    text = " ".join(vals)
    if "papahanaumokuakea" in text or "papahānaumokuākea" in text:
        return "PNMS"
    if "humpback whale" in text:
        return "HIHWNMS"
    if "american samoa" in text:
        return "NMSAS"
    if "flower garden" in text:
        return "FGBNMS"
    if "florida keys" in text:
        return "FKNMS"
    return None


def grid(x: float) -> float:
    """Nearest cell center on NOAA's 0.05 degree grid (-179.975 ... 179.975)."""
    return round((math.floor((x + 180) / 0.05) + 0.5) * 0.05 - 180, 3)


def unwrap(ring: list, anchor: float) -> list[tuple[float, float]]:
    return [(lon + 360 * round((anchor - lon) / 360), lat) for lon, lat, *_ in ring]


def in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def in_polygon(lon: float, lat: float, rings: list) -> bool:
    outer = unwrap(rings[0], lon)
    x = lon + 360 * round((outer[0][0] - lon) / 360)
    return in_ring(x, lat, outer) and not any(in_ring(x, lat, unwrap(r, x)) for r in rings[1:])


def station_candidates(rings: list) -> list[tuple[float, float, str]]:
    """Choose up to two grid centers inside, or close to, one polygon."""
    first = rings[0]
    anchor = first[0][0]
    coords = unwrap(first, anchor)
    west, east = min(v[0] for v in coords), max(v[0] for v in coords)
    south, north = min(v[1] for v in coords), max(v[1] for v in coords)
    candidates = []
    # Search interior over a small, fixed lattice; never enumerate a huge sanctuary grid.
    for j in range(17):
        for i in range(17):
            x = grid(west + (i + 0.5) * (east - west) / 17)
            y = grid(south + (j + 0.5) * (north - south) / 17)
            lon = ((x + 180) % 360) - 180
            if in_polygon(lon, y, rings):
                candidates.append((round(lon, 3), y))
    # Narrow polygons can be missed by the coarse lattice; try bbox center and vertices.
    for x, y in [(0.5 * (west + east), 0.5 * (south + north))] + coords[::max(1, len(coords) // 60)]:
        lon = ((grid(x) + 180) % 360) - 180
        lat = grid(y)
        if in_polygon(lon, lat, rings):
            candidates.append((round(lon, 3), lat))
    candidates = sorted(set(candidates))
    if not candidates:
        # A narrow/small unit may hold no 5km grid-cell center. Explicitly flag
        # a near-boundary fallback so it can never masquerade as an inside pixel.
        x, y = min(coords, key=lambda p: ((p[0] - (west + east) / 2) * math.cos(math.radians(p[1]))) ** 2 + (p[1] - (south + north) / 2) ** 2)
        lon, lat = ((grid(x) + 180) % 360) - 180, grid(y)
        return [(round(lon, 3), lat, "near_boundary")]
    # One close to the bbox center, then a spatially distant second sample.
    mid = (0.5 * (west + east), 0.5 * (south + north))
    first_pick = min(candidates, key=lambda p: (p[0] - mid[0]) ** 2 * math.cos(math.radians(p[1])) ** 2 + (p[1] - mid[1]) ** 2)
    far = max(candidates, key=lambda p: ((p[0] - first_pick[0]) * math.cos(math.radians(p[1]))) ** 2 + (p[1] - first_pick[1]) ** 2)
    return [(p[0], p[1], "inside") for p in ([first_pick] if far == first_pick else [first_pick, far])]


def esri_polygons(rings: list) -> list[list]:
    """Group clockwise Esri exterior rings with contained counterclockwise holes."""
    def signed_area(r):
        coords = unwrap(r, r[0][0])
        return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(coords, coords[1:] + coords[:1])) / 2
    outer = [[r] for r in rings if signed_area(r) < 0]
    holes = [r for r in rings if signed_area(r) >= 0]
    if not outer:
        raise RuntimeError("ArcGIS polygon lacks clockwise exterior rings; inspect boundary geometry")
    for hole in holes:
        x, y = hole[0][:2]
        parent = next((p for p in outer if in_ring(x, y, unwrap(p[0], x))), None)
        if parent is None:
            raise RuntimeError("ArcGIS polygon hole had no containing exterior ring")
        parent.append(hole)
    return outer


def fetch_boundary_features() -> list[dict]:
    print("Fetching ONMS sanctuary boundaries to choose 5 km pixels…", flush=True)
    params = {"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": "4326", "f": "json"}
    url = BOUNDARY_URL + "?" + urllib.parse.urlencode(params)
    try:
        obj = json.loads(get(url))
    except RuntimeError:
        obj = {}
    if "error" in obj or "features" not in obj:
        params["f"] = "geojson"
        obj = json.loads(get(BOUNDARY_URL + "?" + urllib.parse.urlencode(params)))
    if "error" in obj or "features" not in obj:
        raise RuntimeError(f"Unexpected NOAA boundary response: {str(obj)[:250]}")
    features = obj["features"]
    if not features:
        raise RuntimeError("NOAA boundary response contained no features")
    return features


def boundary_polygons(geom: dict) -> list[list]:
    if "rings" in geom:
        return esri_polygons(geom["rings"])
    if geom.get("type") == "Polygon":
        return [geom["coordinates"]]
    if geom.get("type") == "MultiPolygon":
        return geom["coordinates"]
    return []


def write_boundary_geojson(features: list[dict]) -> None:
    """Cache the same ONMS source geometry used for the fixed-pixel selection."""
    chosen = []
    for feat in features:
        props = feat.get("properties") or feat.get("attributes") or {}
        code = code_for(props)
        if not code:
            continue
        polygons = boundary_polygons(feat.get("geometry") or {})
        if not polygons:
            continue
        closed = []
        for poly in polygons:
            rings = []
            for ring in poly:
                coords = [[float(v[0]), float(v[1])] for v in ring]
                if coords and coords[0] != coords[-1]:
                    coords.append(coords[0])
                if len(coords) >= 4:
                    rings.append(coords)
            if rings:
                closed.append(rings)
        if not closed:
            continue
        oid = next((v for k, v in props.items() if k.lower() in ("objectid", "fid")), "")
        chosen.append({"type": "Feature", "properties": {"sanctuary": code, "boundary_objectid": oid},
                       "geometry": {"type": "MultiPolygon", "coordinates": closed}})
    found = {f["properties"]["sanctuary"] for f in chosen}
    if found != set(SITES):
        raise RuntimeError(f"Boundary export omitted {sorted(set(SITES) - found)}; existing boundary file retained")
    output = {"type": "FeatureCollection", "features": chosen, "source_url": BOUNDARY_URL,
              "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "coordinate_system": "EPSG:4326"}
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / "sanctuary_boundaries.geojson"
    temp = path.with_suffix(".geojson.tmp")
    temp.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    os.replace(temp, path)
    print(f"Saved {len(chosen)} sanctuary boundary features to {path}", flush=True)


def get_stations(refresh: bool = False) -> list[dict]:
    path = DATA / "stations.csv"
    if path.exists() and not refresh:
        stations = read_csv(path)
        print(f"Using {len(stations)} previously selected stations in {path}", flush=True)
        return stations
    features = fetch_boundary_features()
    out = []
    for feat in features:
        props = feat.get("properties") or feat.get("attributes") or {}
        code = code_for(props)
        if not code:
            continue
        polys = boundary_polygons(feat.get("geometry") or {})
        oid = next((v for k, v in props.items() if k.lower() in ("objectid", "fid")), "")
        for part, rings in enumerate(polys, 1):
            for pick, (lon, lat, relation) in enumerate(station_candidates(rings), 1):
                out.append({"sanctuary": code, "station_id": f"{code}-{oid}-{part}-{pick}", "latitude": lat, "longitude": lon,
                            "spatial_relation": relation, "boundary_objectid": oid, "geometry_source": BOUNDARY_URL})
    found = {r["sanctuary"] for r in out}
    if found != set(SITES):
        raise RuntimeError(f"Could not select cells for {sorted(set(SITES) - found)}. Check boundary schema and grid selection; no station file written.")
    # Fail safely rather than silently accept an unexpectedly huge response.
    if len(out) > 100:
        raise RuntimeError(f"Selected {len(out)} cells; inspect sanctuary geometry before downloading")
    write_boundary_geojson(features)
    atomic_csv(path, STATION_FIELDS, out)
    print(f"Saved {len(out)} fixed grid stations in {len(found)} sanctuaries to {path}", flush=True)
    return out


def query_station_window(station: dict, start_year: int, end_year: int, current: bool) -> list[dict]:
    lat, lon = float(station["latitude"]), float(station["longitude"])
    # Request recent years first; bounded windows avoid a single 500-month query.
    stop = "last" if current else f"{end_year}-12-20T12:00:00Z"
    rows = None
    used_source = None
    errors = []
    for endpoint, dataset, query_lon in [(ERDDAP, "CRW_sst_v3_1_monthly", lon % 360),
                                         (BACKUP_ERDDAP, "NOAA_DHW_monthly", lon)]:
        constraint = f"sea_surface_temperature[({start_year}-01-31T12:00:00Z):1:({stop})][({lat})][({round(query_lon, 3)})]"
        url = endpoint + "?" + urllib.parse.quote(constraint, safe="[]():-.,")
        try:
            rows = list(csv.reader(io.StringIO(get(url, retries=1, timeout=50).decode("utf-8-sig"))))
            used_source = dataset
            break
        except RuntimeError as exc:
            errors.append(str(exc))
            print(f"  Trying alternate NOAA endpoint for {start_year}–{end_year}…", flush=True)
    if rows is None:
        raise RuntimeError(f"Both NOAA SST servers failed for {station['station_id']} {start_year}–{end_year}: " + " | ".join(errors))
    if len(rows) < 2 or "time" not in rows[0]:
        raise RuntimeError(f"Unexpected ERDDAP response for {station['station_id']}: {str(rows[:2])[:200]}")
    head = rows[0]
    out = []
    for record in rows[2:]:  # ERDDAP CSV has a second units row.
        if len(record) != len(head):
            continue
        val = record[head.index("sea_surface_temperature")]
        if not val or val.lower() == "nan":
            continue
        number = float(val)
        if not -2 <= number <= 50:
            continue
        out.append({"month": record[head.index("time")][:7], "sanctuary": station["sanctuary"], "station_id": station["station_id"],
                    "latitude": station["latitude"], "longitude": station["longitude"], "sst_c": round(number, 4), "source_dataset": used_source + " / sea_surface_temperature"})
    return out


def aggregate(pixels: list[dict], stations: list[dict]) -> list[dict]:
    station_counts = {code: sum(s["sanctuary"] == code for s in stations) for code in SITES}
    groups: dict[tuple[str, str], list[float]] = {}
    for row in pixels:
        groups.setdefault((row["month"], row["sanctuary"]), []).append(float(row["sst_c"]))
    # Baseline must be independently available for every calendar month.
    baseline: dict[tuple[str, int], float] = {}
    for code in SITES:
        for month in range(1, 13):
            vals = [statistics.mean(v) for (m, s), v in groups.items() if s == code and 1991 <= int(m[:4]) <= 2020 and int(m[5:]) == month]
            if len(vals) >= 20:
                baseline[(code, month)] = statistics.mean(vals)
    rows = []
    for (month, code), vals in sorted(groups.items()):
        n = station_counts[code]
        avg = statistics.mean(vals)
        ref = baseline.get((code, int(month[5:])))
        rows.append({"month": month, "sanctuary": code, "mean_sst_c": round(avg, 4), "min_sst_c": round(min(vals), 4),
                     "max_sst_c": round(max(vals), 4), "n_valid": len(vals), "n_stations": n, "coverage_pct": round(100 * len(vals) / n, 1),
                     "anomaly_c": round(avg - ref, 4) if ref is not None else "", "source_dataset": SOURCE,
                     "spatial_method": "unweighted mean of fixed selected 5km pixels in or near boundaries"})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh-stations", action="store_true", help="Rebuild selected cells from current ONMS boundaries (invalidates historical station series).")
    ap.add_argument("--export-boundaries", action="store_true", help="Download ONMS boundaries for the viewer without requesting SST or changing fixed stations.")
    ap.add_argument("--start-year", type=int, default=1985, help="Historical start, default 1985; new series only")
    args = ap.parse_args()
    print(f"Saving outputs to {DATA.resolve()}", flush=True)
    if args.export_boundaries:
        write_boundary_geojson(fetch_boundary_features())
        return
    stations = get_stations(args.refresh_stations)
    old = [] if args.refresh_stations else read_csv(DATA / "sst_pixels_monthly.csv")
    progress_path = DATA / "download_progress.json"
    progress = {} if args.refresh_stations or not progress_path.exists() else json.loads(progress_path.read_text(encoding="utf-8"))
    this_year = dt.datetime.now(dt.timezone.utc).year
    windows = [(y, min(y + 4, this_year)) for y in range(args.start_year, this_year + 1, 5)][::-1]
    print(f"Requesting {len(stations)} NOAA station series in {len(windows)} time windows each, newest first", flush=True)
    merged = {(r["month"], r["station_id"]): r for r in old if r["station_id"] in {s["station_id"] for s in stations}}
    received = 0
    for idx, station in enumerate(stations, 1):
        station_id = station["station_id"]
        print(f"[{idx}/{len(stations)}] {station_id}", flush=True)
        for first, last in windows:
            key = f"{first}-{last}"
            if key in progress.get(station_id, []) and last < this_year:
                continue
            print(f"  Fetching {first}–{last}…", flush=True)
            fresh = query_station_window(station, first, last, last == this_year)
            if not fresh:
                print(f"  WARNING: no valid SST in {first}–{last} (possibly land/masked)", file=sys.stderr, flush=True)
            received += len(fresh)
            merged.update({(r["month"], r["station_id"]): r for r in fresh})
            progress.setdefault(station_id, [])
            if key not in progress[station_id]:
                progress[station_id].append(key)
            # Save the data before marking the window complete, so interruption
            # between writes can only cause a harmless re-fetch of that window.
            pixels = [merged[key] for key in sorted(merged)]
            if pixels:
                atomic_csv(DATA / "sst_pixels_monthly.csv", PIXEL_FIELDS, pixels)
                atomic_csv(DATA / "sst_monthly.csv", MONTH_FIELDS, aggregate(pixels, stations))
            atomic_json(progress_path, progress)
            print(f"  Received {len(fresh)} valid months; saved SST checkpoint", flush=True)
    if not received and not merged:
        raise RuntimeError("No valid SST returned from NOAA; previous CSVs were retained")
    pixels = [merged[key] for key in sorted(merged)]
    summary = aggregate(pixels, stations)
    atomic_csv(DATA / "sst_pixels_monthly.csv", PIXEL_FIELDS, pixels)
    atomic_csv(DATA / "sst_monthly.csv", MONTH_FIELDS, summary)
    atomic_json(DATA / "run_metadata.json", {"updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "monthly_source": ERDDAP, "alternate_source": BACKUP_ERDDAP, "boundary_source": BOUNDARY_URL, "station_count": len(stations), "first_month": summary[0]["month"],
        "last_month": summary[-1]["month"], "method": "Fixed selected 5km pixels in or near each ONMS polygon; unweighted monthly mean. NOAA monthly composite SST."})
    print(f"Wrote {len(summary)} sanctuary-month rows, {len(pixels)} station-month rows; last month {summary[-1]['month']}")


if __name__ == "__main__":
    main()
