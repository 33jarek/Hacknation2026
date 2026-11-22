from __future__ import annotations

from typing import Dict

from .http import fetch_json

SOIL_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

PROPERTIES = ["sand", "clay", "silt", "soc", "cec", "phh2o"]
DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]


def _extract_mean(layer: Dict) -> float:
    values = []
    factor = layer.get("unit_measure", {}).get("d_factor", 1) or 1
    for depth in layer.get("depths", []):
        mean_value = depth.get("values", {}).get("mean")
        if mean_value is not None:
            values.append(float(mean_value) / factor)
    return round(sum(values) / len(values), 2) if values else 0.0


def get_soil_context(lat: float, lon: float) -> Dict:
    payload = fetch_json(
        SOIL_URL,
        params={
            "lon": lon,
            "lat": lat,
            "property": PROPERTIES,
            "depth": DEPTHS,
            "value": "mean",
        },
        timeout=45,
        cache_ttl_seconds=60 * 60 * 24 * 7,
    )

    layers = {layer["name"]: layer for layer in payload.get("properties", {}).get("layers", [])}
    sand = _extract_mean(layers.get("sand", {}))
    clay = _extract_mean(layers.get("clay", {}))
    silt = _extract_mean(layers.get("silt", {}))
    soc = _extract_mean(layers.get("soc", {}))
    cec = _extract_mean(layers.get("cec", {}))
    ph = _extract_mean(layers.get("phh2o", {}))

    retention_score = 50
    if sand >= 60:
        retention_score += 25
    if clay >= 30:
        retention_score -= 10
    if soc >= 18:
        retention_score -= 10
    if cec >= 18:
        retention_score -= 5
    retention_score = max(0, min(100, retention_score))

    if retention_score >= 70:
        retention_class = "low"
    elif retention_score >= 45:
        retention_class = "medium"
    else:
        retention_class = "good"

    return {
        "sand_pct": sand,
        "clay_pct": clay,
        "silt_pct": silt,
        "soil_organic_carbon_g_per_kg": soc,
        "cec_cmolc_per_kg": cec,
        "ph_h2o": ph,
        "water_holding_risk_score": retention_score,
        "water_holding_class": retention_class,
    }
