from __future__ import annotations

import math
from typing import Dict, List

import urllib.parse

from .http import _build_cache_key, fetch_json, fetch_text

ULDK_URL = "https://uldk.gugik.gov.pl/"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ADDRESS_TYPES = {"address", "building", "house", "place", "residential"}


def _parse_coordinate_ring(text: str) -> List[List[float]]:
    coordinates = []
    for pair in text.split(","):
        parts = pair.replace("(", " ").replace(")", " ").split()
        if len(parts) < 2:
            continue
        coordinates.append([float(parts[0]), float(parts[1])])
    if len(coordinates) < 4:
        raise ValueError("Niepełna geometria działki")
    return coordinates


def _split_top_level_groups(text: str) -> List[str]:
    groups = []
    depth = 0
    start = None
    for index, char in enumerate(text):
        if char == "(":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and start is not None:
                groups.append(text[start:index])
                start = None
    if depth != 0 or not groups:
        raise ValueError("Nieobsługiwany format geometrii")
    return groups


def parse_wkt_polygon(wkt: str) -> Dict:
    if not wkt.startswith("SRID="):
        raise ValueError("Nieobsługiwany format geometrii")
    _, geometry = wkt.split(";", 1)
    geometry = geometry.strip()
    upper = geometry.upper()

    if upper.startswith("POLYGON"):
        body = geometry[geometry.find("("):]
        polygon_body = _split_top_level_groups(body)[0]
        rings = [_parse_coordinate_ring(group) for group in _split_top_level_groups(polygon_body)]
        return {"type": "Polygon", "coordinates": rings}

    if upper.startswith("MULTIPOLYGON"):
        body = geometry[geometry.find("("):]
        polygons = []
        for polygon_body in _split_top_level_groups(_split_top_level_groups(body)[0]):
            rings = [_parse_coordinate_ring(group) for group in _split_top_level_groups(polygon_body)]
            polygons.append(rings)
        return {"type": "MultiPolygon", "coordinates": polygons}

    raise ValueError("Nieobsługiwany format geometrii")


def _polygons(geometry: Dict) -> List[List[List[List[float]]]]:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    raise ValueError("Nieobsługiwany format geometrii")


def _ring_points(ring: List[List[float]]) -> List[List[float]]:
    if len(ring) > 1 and ring[0] == ring[-1]:
        return ring[:-1]
    return ring


def _all_points(geometry: Dict) -> List[List[float]]:
    points = []
    for polygon in _polygons(geometry):
        for ring in polygon:
            points.extend(ring)
    if not points:
        raise ValueError("Pusta geometria działki")
    return points


def polygon_bbox(geometry: Dict) -> List[float]:
    points = _all_points(geometry)
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return [min(lons), min(lats), max(lons), max(lats)]


def _ring_area_m2(ring: List[List[float]]) -> float:
    filtered = _ring_points(ring)
    if len(filtered) < 3:
        return 0.0
    centroid_lat = sum(point[1] for point in filtered) / len(filtered)
    centroid_lon = sum(point[0] for point in filtered) / len(filtered)
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * math.cos(math.radians(centroid_lat))
    projected = [
        ((point[0] - centroid_lon) * lon_scale, (point[1] - centroid_lat) * lat_scale)
        for point in filtered
    ]
    area = 0.0
    for index, (x1, y1) in enumerate(projected):
        x2, y2 = projected[(index + 1) % len(projected)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def polygon_centroid(geometry: Dict) -> Dict[str, float]:
    largest_ring = None
    largest_area = -1.0
    for polygon in _polygons(geometry):
        exterior = polygon[0]
        area = _ring_area_m2(exterior)
        if area > largest_area:
            largest_area = area
            largest_ring = exterior
    if not largest_ring:
        raise ValueError("Pusta geometria działki")
    filtered = _ring_points(largest_ring)
    return {
        "lon": sum(point[0] for point in filtered) / len(filtered),
        "lat": sum(point[1] for point in filtered) / len(filtered),
    }


def polygon_area_ha(geometry: Dict) -> float:
    total = 0.0
    for polygon in _polygons(geometry):
        if not polygon:
            continue
        total += _ring_area_m2(polygon[0])
        for hole in polygon[1:]:
            total -= _ring_area_m2(hole)
    return round(max(total, 0.0) / 10_000.0, 2)


def _swap_xy(geometry: Dict) -> Dict:
    def swap_ring(ring):
        return [[point[1], point[0]] for point in ring]

    if geometry["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [swap_ring(r) for r in geometry["coordinates"]]}
    return {
        "type": "MultiPolygon",
        "coordinates": [[swap_ring(r) for r in polygon] for polygon in geometry["coordinates"]],
    }


def parse_uldk_response(raw: str) -> Dict:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    # GetParcelById/ByXY: "0" = OK; GetParcelByIdOrNr: liczba wyników.
    if not lines or not lines[0].isdigit() or lines[0] == "-1":
        raise ValueError("Nie znaleziono działki")
    data_lines = [line for line in lines[1:] if "|" in line]
    if not data_lines:
        raise ValueError("Niepełna odpowiedź usługi działek")
    values = data_lines[0].split("|")
    if len(values) < 8:
        raise ValueError("Niepełna odpowiedź usługi działek")

    geometry = parse_wkt_polygon(values[7])
    # Zabezpieczenie: w Polsce lon ∈ (14, 25), lat ∈ (49, 55). Jeśli odwrotnie – zamień.
    first = _all_points(geometry)[0]
    if 49.0 <= first[0] <= 55.5 and 13.5 <= first[1] <= 24.5:
        geometry = _swap_xy(geometry)
    return {
        "id": values[0],
        "teryt": values[1],
        "parcel_number": values[2],
        "voivodeship": values[3],
        "county": values[4],
        "commune": values[5],
        "region": values[6],
        "geometry": geometry,
        "bbox": polygon_bbox(geometry),
        "centroid": polygon_centroid(geometry),
        "area_ha": polygon_area_ha(geometry),
    }


class ParcelServiceError(RuntimeError):
    """Usługa ULDK niedostępna / odrzuciła zapytanie (to nie jest 'brak działki')."""


def _lookup(params: Dict[str, str]) -> Dict:
    raw = fetch_text(ULDK_URL, params=params, timeout=8, cache_ttl_seconds=60 * 60 * 24 * 30)
    try:
        return parse_uldk_response(raw)
    except ValueError as exc:
        # Nie trzymaj w cache błędnych / zablokowanych odpowiedzi.
        url = f"{ULDK_URL}?{urllib.parse.urlencode(params, doseq=True)}"
        _build_cache_key("GET", url, None).unlink(missing_ok=True)
        lines = raw.strip().splitlines()
        if lines and lines[0].strip() == "0" and "|" not in raw:
            raise ParcelServiceError(
                "Usługa ULDK (GUGiK) odrzuciła zapytanie – prawdopodobnie chwilowa blokada lub przeciążenie"
            ) from exc
        raise


def lookup_parcel_by_id(parcel_id: str) -> Dict:
    return _lookup(
        {
            "request": "GetParcelById",
            "id": parcel_id,
            "result": "id,teryt,parcel,voivodeship,county,commune,region,geom_wkt",
            "srid": "4326",
        }
    )


def lookup_parcel_by_id_or_nr(query: str) -> Dict:
    """Pełny identyfikator (141201_1.0001.6509) albo 'Obręb numer', np. 'Krzyki 33/1'."""
    return _lookup(
        {
            "request": "GetParcelByIdOrNr",
            "id": query,
            "result": "id,teryt,parcel,voivodeship,county,commune,region,geom_wkt",
            "srid": "4326",
        }
    )


def lookup_parcel_by_point(lat: float, lon: float) -> Dict:
    return _lookup(
        {
            "request": "GetParcelByXY",
            "xy": f"{lon},{lat},4326",
            "result": "id,teryt,parcel,voivodeship,county,commune,region,geom_wkt",
            "srid": "4326",
        }
    )


def _address_rank(item: Dict) -> int:
    kind = item.get("addresstype") or item.get("type") or ""
    return 0 if kind in ADDRESS_TYPES else 1


def geocode_address(query: str) -> Dict:
    results = fetch_json(
        NOMINATIM_URL,
        params={
            "format": "jsonv2",
            "countrycodes": "pl",
            "limit": 5,
            "layer": "address",
            "q": query,
        },
        timeout=20,
        cache_ttl_seconds=60 * 60 * 24 * 7,
    )
    if not results:
        raise ValueError("Nie znaleziono adresu w Polsce")
    chosen = sorted(results, key=_address_rank)[0]
    return {
        "lat": float(chosen["lat"]),
        "lon": float(chosen["lon"]),
        "label": chosen.get("display_name") or query,
    }


def lookup_parcel_by_address(query: str) -> Dict:
    point = geocode_address(query.strip())
    try:
        parcel = lookup_parcel_by_point(point["lat"], point["lon"])
    except ValueError as exc:
        raise ValueError("Adres został znaleziony, ale nie wskazuje działki ewidencyjnej") from exc
    parcel["matched_address"] = point["label"]
    parcel["address_point"] = {"lat": point["lat"], "lon": point["lon"]}
    return parcel


NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"


def reverse_geocode(lat: float, lon: float) -> str | None:
    """Krótka nazwa miejscowości/gminy dla punktu (best-effort)."""
    try:
        result = fetch_json(
            NOMINATIM_REVERSE_URL,
            params={
                "format": "jsonv2",
                "lat": f"{lat:.5f}",
                "lon": f"{lon:.5f}",
                "zoom": 14,
                "accept-language": "pl",
            },
            timeout=10,
            cache_ttl_seconds=60 * 60 * 24 * 30,
        )
    except Exception:
        return None
    address = result.get("address") or {}
    place = (
        address.get("village")
        or address.get("town")
        or address.get("city")
        or address.get("hamlet")
        or address.get("suburb")
        or address.get("municipality")
    )
    region = address.get("county") or address.get("state")
    if place and region and region != place:
        return f"{place}, {region}"
    return place or region or result.get("display_name")
