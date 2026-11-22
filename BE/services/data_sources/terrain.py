from __future__ import annotations

from typing import Dict, List

from .http import fetch_json

TOPO_URL = "https://api.opentopodata.org/v1/srtm30m"


def _offset_points(lat: float, lon: float) -> List[str]:
    delta = 0.002
    points = [
        f"{lat},{lon}",
        f"{lat + delta},{lon}",
        f"{lat - delta},{lon}",
        f"{lat},{lon + delta}",
        f"{lat},{lon - delta}",
    ]
    return points


def get_terrain_context(lat: float, lon: float) -> Dict:
    payload = fetch_json(
        TOPO_URL,
        params={"locations": "|".join(_offset_points(lat, lon))},
        timeout=30,
        cache_ttl_seconds=60 * 60 * 24 * 30,
    )
    elevations = [result.get("elevation") for result in payload.get("results", []) if result.get("elevation") is not None]
    if not elevations:
        raise ValueError("Brak danych wysokościowych")
    local_relief = round(max(elevations) - min(elevations), 1)
    if local_relief < 5:
        terrain_class = "flat"
    elif local_relief < 15:
        terrain_class = "gently undulating"
    else:
        terrain_class = "rolling"

    runoff_risk = min(100, int(local_relief * 4.5))
    return {
        "elevation_m": round(elevations[0], 1),
        "local_relief_m": local_relief,
        "terrain_class": terrain_class,
        "runoff_risk_score": runoff_risk,
    }
