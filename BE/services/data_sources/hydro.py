from __future__ import annotations

from typing import Dict, List

from .http import fetch_form_json

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def get_hydro_context(lat: float, lon: float) -> Dict:
    query = f"""
    [out:json][timeout:12];
    (
      nwr(around:800,{lat},{lon})["waterway"];
      nwr(around:800,{lat},{lon})["natural"="water"];
      nwr(around:800,{lat},{lon})["landuse"="reservoir"];
    );
    out tags center 20;
    """
    payload = fetch_form_json(OVERPASS_URL, {"data": query}, timeout=20, cache_ttl_seconds=60 * 60 * 24)
    features = payload.get("elements", [])
    names: List[str] = []
    waterway_count = 0
    for feature in features:
        tags = feature.get("tags", {})
        if tags.get("waterway") or tags.get("natural") == "water" or tags.get("landuse") == "reservoir":
            waterway_count += 1
        if tags.get("name"):
            names.append(tags["name"])

    unique_names = []
    for name in names:
        if name not in unique_names:
            unique_names.append(name)

    if waterway_count >= 6:
        hydro_class = "strong"
    elif waterway_count >= 2:
        hydro_class = "moderate"
    else:
        hydro_class = "limited"

    return {
        "nearby_water_features": waterway_count,
        "hydro_connection_class": hydro_class,
        "feature_names": unique_names[:5],
    }
