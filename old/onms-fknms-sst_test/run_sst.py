#!/usr/bin/env python3
"""Build NOAA CoralTemp monthly SST for FKNMS native in-boundary grid centers.

Run once with ``python run_sst.py`` (or F5 in IDLE). Completed year/band
checkpoints are reused; the current year is refreshed. Python standard library.
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
import pathlib
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CHUNKS = DATA / "chunks"
BOUNDARY_URL = "https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services/NMS_Boundaries_02032022/FeatureServer/0/query"
ERDDAP = "https://oceanwatch.pifsc.noaa.gov/erddap/griddap/CRW_sst_v3_1_monthly.csv"
BACKUP_ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW_monthly.csv"
SOURCE = "NOAA Coral Reef Watch CoralTemp v3.1 monthly mean"
SITES = ("FKNMS",)
STATION_FIELDS = ["sanctuary", "station_id", "latitude", "longitude", "spatial_relation", "boundary_objectid", "geometry_source"]
PIXEL_FIELDS = ["month", "sanctuary", "station_id", "latitude", "longitude", "sst_c", "source_dataset"]
MONTH_FIELDS = ["month", "sanctuary", "mean_sst_c", "min_sst_c", "max_sst_c", "n_valid", "n_stations", "coverage_pct", "anomaly_c", "source_dataset", "spatial_method"]
METHOD = "all native 0.05 degree grid centers inside ONMS boundary; cosine latitude weighted valid-cell mean"


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
    if any(v.strip().upper() == "GRNMS" for v in properties.values() if isinstance(v, str)) or "gray's reef" in text or "grays reef" in text:
        return "GRNMS"
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

def write_boundary_geojson(features: list[dict], target: pathlib.Path | None = None, sites: set[str] | None = None) -> None:
    """Cache the same ONMS source geometry used for the fixed-pixel selection."""
    requested = sites if sites is not None else set(SITES)
    chosen = []
    for feat in features:
        props = feat.get("properties") or feat.get("attributes") or {}
        code = code_for(props)
        if code not in requested:
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
    if found != requested:
        raise RuntimeError(f"Boundary export omitted {sorted(requested - found)}; existing boundary file retained")
    output = {"type": "FeatureCollection", "features": chosen, "source_url": BOUNDARY_URL,
              "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "coordinate_system": "EPSG:4326"}
    DATA.mkdir(parents=True, exist_ok=True)
    path = target or (DATA / "sanctuary_boundaries.geojson")
    temp = path.with_suffix(".geojson.tmp")
    temp.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    os.replace(temp, path)
    print(f"Saved {len(chosen)} sanctuary boundary features to {path}", flush=True)

def boundary_data() -> dict:
    path = DATA / "sanctuary_boundaries.geojson"
    if not path.exists():
        print("FKNMS boundary GeoJSON absent; retrieving NOAA ONMS polygons once…", flush=True)
        write_boundary_geojson(fetch_boundary_features(), target=path, sites=set(SITES))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("type") != "FeatureCollection" or not obj.get("features"):
        raise RuntimeError("Boundary GeoJSON lacks sanctuary polygons")
    found = {f.get("properties", {}).get("sanctuary") for f in obj["features"]}
    if not set(SITES).issubset(found):
        raise RuntimeError(f"Boundary GeoJSON is missing {sorted(set(SITES) - found)}; no stations were changed")
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
        stride = 1  # Every 0.05° native cell center.
        polygons = boundary_polygons(feat.get("geometry") or {})
        for rings in polygons:
            exterior = unwrap(rings[0], rings[0][0][0])
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
                    if not in_polygon(lon, lat, rings):
                        continue
                    inside_count += 1
                    key = site, j, im
                    stations[key] = {"sanctuary": site, "station_id": f"{site}-y{j}-x{im}",
                        "latitude": lat, "longitude": lon, "spatial_relation": "inside",
                        "boundary_objectid": props.get("boundary_objectid", ""),
                        "geometry_source": boundaries.get("source_url", BOUNDARY_URL)}
            component_counts[site].append(inside_count)
    result = [stations[k] for k in sorted(stations)]
    counts = {s: sum(r["sanctuary"] == s for r in result) for s in SITES}
    for site, count in counts.items():
        if count == 0:
            raise RuntimeError(f"No interior {site} grid centers selected; inspect boundary geometry before retrieval")
        if count < 20:
            print(f"CAUTION: {site} has only {count} interior native-grid cells; this is a coarse-resolution indicator", flush=True)
        missed = sum(n == 0 for n in component_counts[site])
        if missed:
            print(f"WARNING: {site} lattice missed {missed} small polygon components; inspect the map", flush=True)
        print(f"{site}: {count} interior cells at 0.05° native grid spacing", flush=True)
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


def request_range(site_stations: list[dict], first: str, last: str, alternate: bool) -> tuple[list[dict], set[str]]:
    site = site_stations[0]["sanctuary"]
    stride = 1
    north = max(float(s["latitude"]) for s in site_stations)
    south = min(float(s["latitude"]) for s in site_stations)
    by_cell = {(int(round((89.975 - float(s["latitude"])) / .05)),
                int(round(((float(s["longitude"]) % 360) - .025) / .05))): s for s in site_stations}
    endpoint = BACKUP_ERDDAP if alternate else ERDDAP
    source = "NOAA_DHW_monthly" if alternate else "CRW_sst_v3_1_monthly"
    result: dict[tuple[str, str], dict] = {}
    observed_months: set[str] = set()
    for west, east in regions(site_stations, alternate):
        constraint = (f"sea_surface_temperature[({first}):1:({last})]"
                      f"[({north}):{stride}:({south})][({west}):{stride}:({east})]")
        url = endpoint + "?" + urllib.parse.quote(constraint, safe="[]():-.,")
        response = get(url, retries=1, timeout=45).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(response))
        fields = reader.fieldnames or []
        if not {"time", "latitude", "longitude", "sea_surface_temperature"}.issubset(fields):
            raise RuntimeError(f"Unexpected ERDDAP columns: {fields}")
        for row in reader:
            month = (row.get("time") or "")[:7]
            if len(month) == 7 and month[4] == "-" and month[:4].isdigit() and month[5:].isdigit():
                observed_months.add(month)  # Also count months in which every cell is masked.
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
            result[month, station["station_id"]] = {"month": month, "sanctuary": site,
                "station_id": station["station_id"], "latitude": station["latitude"],
                "longitude": station["longitude"], "sst_c": round(value, 4),
                "source_dataset": source + " / sea_surface_temperature"}
    return [result[k] for k in sorted(result)], observed_months


def quarter_windows(year: int, current_year: int) -> list[tuple[int, str, str, set[str] | None]]:
    """Newest quarter first; the current quarter ends at the dataset's last time."""
    current_month = dt.datetime.now(dt.timezone.utc).month
    result = []
    for quarter in (4, 3, 2, 1):
        first_month = quarter * 3 - 2
        if year == current_year and first_month > current_month:
            continue
        last_month = first_month + 2
        first = f"{year}-{first_month:02d}-{calendar.monthrange(year, first_month)[1]:02d}T12:00:00Z"
        active = year == current_year and first_month <= current_month <= last_month
        last = "last" if active else f"{year}-{last_month:02d}-{calendar.monthrange(year, last_month)[1]:02d}T12:00:00Z"
        expected = None if active else {f"{year}-{m:02d}" for m in range(first_month, last_month + 1)}
        result.append((quarter, first, last, expected))
    return result


def fetch_quarter(stations: list[dict], first: str, last: str, expected: set[str] | None) -> tuple[list[dict], set[str]]:
    errors = []
    for alternate in (False, True):
        name = "CoastWatch fallback" if alternate else "OceanWatch primary"
        print(f"    {name}: {first[:7]} through {last[:7] if last != 'last' else 'latest'} ({len(stations)} cells)", flush=True)
        try:
            rows, months = request_range(stations, first, last, alternate)
            if expected is not None and not expected.issubset(months):
                raise RuntimeError(f"Missing monthly slices: {sorted(expected - months)}")
            if not months:
                raise RuntimeError("No monthly slices returned")
            return rows, months
        except RuntimeError as exc:
            errors.append(str(exc))
            print(f"    {name} failed: {exc}", flush=True)
    if expected is not None:
        print("    Retrying this quarter one month at a time…", flush=True)
        combined = []
        observed = set()
        for month in sorted(expected):
            year, number = map(int, month.split("-"))
            stamp = f"{month}-{calendar.monthrange(year, number)[1]:02d}T12:00:00Z"
            for alternate in (False, True):
                print(f"      {month}: {'CoastWatch' if alternate else 'OceanWatch'}", flush=True)
                try:
                    rows, months = request_range(stations, stamp, stamp, alternate)
                    if month not in months:
                        raise RuntimeError("Monthly slice missing")
                    combined.extend(rows)
                    observed.update(months)
                    break
                except RuntimeError as exc:
                    if alternate:
                        raise RuntimeError(f"{month} failed on both NOAA endpoints: {exc}. Rerun to resume") from exc
        return combined, observed
    raise RuntimeError("Both NOAA endpoints failed for this quarter. Rerun to resume. " + " | ".join(errors))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    atomic_csv(path, fields, rows)


def aggregate_spatial(pixel_files: list[Path], stations: list[dict], available_months: set[str]) -> list[dict]:
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
    for month in sorted(available_months):
      for site in SITES:
        group = groups.get((month, site))
        mean = means.get((month, site))
        reference = baseline.get((site, int(month[5:])))
        summary.append({"month": month, "sanctuary": site, "mean_sst_c": round(mean, 4) if mean is not None else "",
            "min_sst_c": round(group["min"], 4) if group else "",
            "max_sst_c": round(group["max"], 4) if group else "",
            "n_valid": group["n"] if group else 0, "n_stations": expected[site],
            "coverage_pct": round(100 * group["n"] / expected[site], 1) if group else 0,
            "anomaly_c": round(mean - reference, 4) if mean is not None and reference is not None else "",
            "source_dataset": SOURCE,
            "spatial_method": METHOD + " (0.05 degree grid)"})
    return summary


def run() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start-year", type=int, default=1985)
    ap.add_argument("--plan-only", action="store_true", help="Write proposed cells and coverage audit without SST requests")
    args = ap.parse_args()
    if args.start_year < 1985 or args.start_year > dt.datetime.now(dt.timezone.utc).year:
        ap.error("--start-year must be between 1985 and the current year")
    print(f"Saving outputs to {DATA.resolve()}", flush=True)
    boundaries = boundary_data()
    stations, audit = lattice_stations(boundaries)
    digest = station_hash(stations)
    CHUNKS.mkdir(parents=True, exist_ok=True)
    state_path = CHUNKS / "selection.json"
    if state_path.exists():
        prior = json.loads(state_path.read_text(encoding="utf-8"))
        if prior.get("station_hash") != digest:
            if any(CHUNKS.glob("*.csv")):
                raise RuntimeError("Boundary or sampling locations changed. Preserve the existing chunks folder and move it aside before a fresh backfill.")
            state_path.unlink()  # A plan with no SST chunks can be safely revised.
    if not state_path.exists():
        atomic_json(state_path, {"station_hash": digest, "grid_spacing_degrees": .05,
            "boundary_retrieved_utc": boundaries.get("retrieved_utc"), "audit": audit})
    write_csv(DATA / "stations.csv", STATION_FIELDS, stations)
    atomic_json(DATA / "sampling_audit.json", {"station_counts": audit["counts"],
        "component_counts": audit["component_counts"], "grid_spacing_degrees": .05,
        "station_hash": digest, "boundary_retrieved_utc": boundaries.get("retrieved_utc"),
        "boundary_file": "sanctuary_boundaries.geojson", "site_codes": list(SITES),
        "method": METHOD, "note": "All native 0.05 degree cell centers inside polygons; boundary-edge partial cells and coral habitat are not separately counted."})
    if args.plan_only:
        print("Station inventory saved. No SST was requested. Inspect stations.csv and sampling_audit.json.")
        return
    this_year = dt.datetime.now(dt.timezone.utc).year
    pixel_files = []
    quarter_files: dict[tuple[int, int], list[Path]] = {}
    selected = stations
    print(f"FKNMS: {len(selected)} in-boundary cells; starting newest quarter first", flush=True)
    for year in range(this_year, args.start_year - 1, -1):
        for quarter, first, last, expected in quarter_windows(year, this_year):
            for tile, tile_stations in latitude_tiles(selected):
                path = CHUNKS / f"FKNMS_{year}_q{quarter}_lat{tile:03d}.csv"
                months_path = path.with_suffix(".months.json")
                pixel_files.append(path)
                quarter_files.setdefault((year, quarter), []).append(months_path)
                if path.exists() and months_path.exists():
                    prior = json.loads(months_path.read_text(encoding="utf-8"))
                    months = set(prior["months"])
                    if prior.get("station_hash") != digest:
                        raise RuntimeError(f"Selection changed in {months_path}; start in a fresh folder")
                    if expected is not None and expected.issubset(months):
                        continue
                print(f"  {year} Q{quarter} latitude band {tile}: requesting {len(tile_stations)} cells", flush=True)
                rows, months = fetch_quarter(tile_stations, first, last, expected)
                if months_path.exists():
                    prior_months = set(json.loads(months_path.read_text(encoding="utf-8"))["months"])
                    if not prior_months.issubset(months):
                        raise RuntimeError(f"New response lost earlier months; preserved {path}")
                write_csv(path, PIXEL_FIELDS, rows)
                atomic_json(months_path, {"months": sorted(months), "station_hash": digest})
                print(f"    Saved {len(rows)} valid pixel observations for {len(months)} months", flush=True)
    if any(not path.exists() for path in pixel_files):
        raise RuntimeError("Incomplete checkpoints; summary was not replaced")
    available_months = set()
    for (year, quarter), paths in quarter_files.items():
        common = None
        for path in paths:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["station_hash"] != digest:
                raise RuntimeError(f"Checkpoint selection changed: {path}")
            months = set(record["months"])
            common = months if common is None else common & months
        available_months.update(common or set())
    if not available_months:
        raise RuntimeError("No common SST months across FKNMS latitude bands")
    summary = aggregate_spatial(pixel_files, stations, available_months)
    atomic_json(CHUNKS / "index.json", {"station_hash": digest,
        "pixel_chunks": [p.name for p in pixel_files], "note": "Each CSV contains valid cell observations for one year and latitude band."})
    write_csv(DATA / "sst_monthly.csv", MONTH_FIELDS, summary)
    atomic_json(DATA / "run_metadata.json", {"updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "station_hash": digest, "boundary_retrieved_utc": boundaries.get("retrieved_utc"),
        "source": ERDDAP, "start_year": args.start_year, "last_month": summary[-1]["month"],
        "station_counts": audit["counts"], "component_counts": audit["component_counts"], "site_codes": list(SITES),
        "method": METHOD, "pixel_chunks_manifest": "chunks/index.json",
        "complete_history": args.start_year == 1985})
    print(f"FKNMS series complete: {len(summary)} sanctuary-month rows. ")


if __name__ == "__main__":
    run()
