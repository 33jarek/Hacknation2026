from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

CROP_PROFILES = {
    "winter_wheat": {"label": "Pszenica ozima", "sensitivity": 0.55, "ndvi_target": 0.48},
    "maize": {"label": "Kukurydza", "sensitivity": 0.8, "ndvi_target": 0.62},
    "potato": {"label": "Ziemniak", "sensitivity": 0.82, "ndvi_target": 0.58},
    "sugar_beet": {"label": "Burak cukrowy", "sensitivity": 0.78, "ndvi_target": 0.6},
    "rapeseed": {"label": "Rzepak", "sensitivity": 0.68, "ndvi_target": 0.5},
    "grassland": {"label": "Użytki zielone", "sensitivity": 0.6, "ndvi_target": 0.55},
    "orchard": {"label": "Sad", "sensitivity": 0.72, "ndvi_target": 0.57},
}


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _bucket(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "moderate"
    return "low"


def _confidence(missing_data: List[str]) -> str:
    if len(missing_data) >= 3:
        return "low"
    if missing_data:
        return "moderate"
    return "high"


def summarize_analysis(parcel: Dict, crop: str, analysis_date: str, signals: Dict, missing_data: List[str]) -> Dict:
    crop_profile = CROP_PROFILES.get(crop, {"label": crop.replace("_", " ").title(), "sensitivity": 0.65, "ndvi_target": 0.5})

    weather = signals.get("weather", {})
    soil = signals.get("soil", {})
    terrain = signals.get("terrain", {})
    hydro = signals.get("hydro", {})
    satellite = signals.get("satellite", {})

    recent_deficit_ratio = max(0.0, weather.get("recent_deficit_ratio", 0.0))
    weather_risk = _clamp(recent_deficit_ratio * 100 + max(weather.get("precipitation_anomaly_ratio", 0.0), 0.0) * 35)
    soil_risk = float(soil.get("water_holding_risk_score", 50))
    historical_risk = _clamp(weather.get("drought_frequency_pct", 0.0) * 0.75 + soil_risk * 0.25)
    retention_potential = _clamp((100 - terrain.get("runoff_risk_score", 40)) * 0.25 + soil_risk * 0.35 + hydro.get("nearby_water_features", 0) * 6)

    satellite_risk = None
    if satellite:
        ndvi_target = crop_profile["ndvi_target"]
        ndvi_gap = max(0.0, ndvi_target - satellite.get("ndvi_mean", ndvi_target))
        satellite_risk = _clamp((ndvi_gap / max(ndvi_target, 0.1)) * 100)

    weighted_components: List[Tuple[str, float, float]] = [
        ("Niedobór opadów", weather_risk, 0.45),
        ("Zdolność gleby do zatrzymywania wody", soil_risk, 0.25),
        ("Powtarzalność suszy", historical_risk, 0.2),
    ]
    if satellite_risk is not None:
        weighted_components.append(("Stres roślinności na zdjęciu satelitarnym", satellite_risk, 0.1))

    weight_sum = sum(weight for _, _, weight in weighted_components) or 1.0
    current_risk_score = round(sum(score * weight for _, score, weight in weighted_components) / weight_sum, 1)

    forecast = weather.get("forecast") or {}
    forecast_dryness = max(0.0, forecast.get("et0_7d_mm", 0.0) - forecast.get("precipitation_7d_mm", 0.0))
    irrigation_need_score = _clamp(current_risk_score * 0.55 + crop_profile["sensitivity"] * 30 + forecast_dryness * 1.4)

    drivers = []
    for name, score, _ in sorted(weighted_components, key=lambda item: item[1], reverse=True)[:3]:
        drivers.append({"name": name, "score": round(score, 1)})

    analysis_summary = {
        "parcel": parcel,
        "crop_key": crop,
        "crop_label": crop_profile["label"],
        "analysis_date": analysis_date,
        "current_status": {
            "risk_score": current_risk_score,
            "risk_level": _bucket(current_risk_score),
            "confidence": _confidence(missing_data),
            "drivers": drivers,
        },
        "historical_context": {
            "susceptibility_score": round(historical_risk, 1),
            "susceptibility_level": _bucket(historical_risk),
            "high_risk_months": weather.get("high_risk_months", []),
            "drought_frequency_pct": weather.get("drought_frequency_pct", 0.0),
        },
        "retention_context": {
            "potential_score": round(retention_potential, 1),
            "potential_level": _bucket(retention_potential),
            "terrain_class": terrain.get("terrain_class"),
            "hydro_connection_class": hydro.get("hydro_connection_class"),
        },
        "irrigation_guidance": {
            "need_score": round(irrigation_need_score, 1),
            "need_level": _bucket(irrigation_need_score),
            "forecast_precipitation_7d_mm": forecast.get("precipitation_7d_mm"),
            "forecast_et0_7d_mm": forecast.get("et0_7d_mm"),
        },
        "signal_snapshot": signals,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    return analysis_summary
