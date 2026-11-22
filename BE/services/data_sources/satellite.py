from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

from .http import fetch_json

STAC_SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
DATA_API_URL = "https://planetarycomputer.microsoft.com/api/data/v1/item/statistics"


def _pick_scene(features: List[Dict]) -> Dict:
    sorted_features = sorted(
        features,
        key=lambda item: (
            item.get("properties", {}).get("eo:cloud_cover", 1000),
            item.get("properties", {}).get("datetime", ""),
        ),
    )
    return sorted_features[0]


def get_satellite_context(geometry: Dict, bbox: List[float], analysis_date: date) -> Dict:
    search_payload = {
        "collections": ["landsat-c2-l2"],
        "bbox": bbox,
        "datetime": f"{(analysis_date - timedelta(days=90)).isoformat()}T00:00:00Z/{analysis_date.isoformat()}T23:59:59Z",
        "limit": 8,
        "query": {"eo:cloud_cover": {"lt": 35}},
    }
    results = fetch_json(
        STAC_SEARCH_URL,
        method="POST",
        json_body=search_payload,
        timeout=45,
        cache_ttl_seconds=60 * 60 * 24,
    )
    features = results.get("features", [])
    if not features:
        raise ValueError("Nie znaleziono aktualnej sceny satelitarnej")

    scene = _pick_scene(features)
    params = {
        "collection": "landsat-c2-l2",
        "item": scene["id"],
        "assets": "nir08,red",
        "expression": "(nir08-red)/(nir08+red)",
        "asset_as_band": "true",
    }
    stats = fetch_json(
        DATA_API_URL,
        method="POST",
        params=params,
        json_body={"type": "Feature", "geometry": geometry, "properties": {}},
        timeout=60,
        cache_ttl_seconds=60 * 60 * 24,
    )
    statistics = stats.get("properties", {}).get("statistics", {})
    ndvi_stats = next(iter(statistics.values()), {})
    ndvi_mean = round(float(ndvi_stats.get("mean", 0.0)), 3)

    if ndvi_mean < 0.2:
        class_name = "very low"
    elif ndvi_mean < 0.4:
        class_name = "low"
    elif ndvi_mean < 0.6:
        class_name = "moderate"
    else:
        class_name = "high"

    return {
        "scene_id": scene["id"],
        "scene_datetime": scene.get("properties", {}).get("datetime"),
        "cloud_cover_pct": scene.get("properties", {}).get("eo:cloud_cover"),
        "ndvi_mean": ndvi_mean,
        "vegetation_class": class_name,
    }
