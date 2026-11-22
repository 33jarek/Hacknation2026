from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Dict, List

from .http import fetch_json

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _parse_iso(day: str) -> date:
    return datetime.strptime(day, "%Y-%m-%d").date()


def _ten_years_back(value: date) -> date:
    try:
        return value.replace(year=value.year - 10)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year - 10)


def _iter_weather_rows(payload: Dict) -> List[Dict]:
    daily = payload.get("daily", {})
    rows = []
    for index, day in enumerate(daily.get("time", [])):
        rows.append(
            {
                "date": _parse_iso(day),
                "precipitation": float(daily.get("precipitation_sum", [0])[index] or 0),
                "temperature_mean": float(daily.get("temperature_2m_mean", [0])[index] or 0),
                "temperature_max": float(daily.get("temperature_2m_max", [0])[index] or 0),
                "et0": float(daily.get("et0_fao_evapotranspiration", [0])[index] or 0),
            }
        )
    return rows


def _sum_metric(rows: List[Dict], key: str) -> float:
    return round(sum(row.get(key, 0.0) for row in rows), 2)


def _safe_ratio(a: float, b: float) -> float:
    if abs(b) < 1e-6:
        return 0.0
    return a / b


def _month_name(month: int) -> str:
    names = {
        1: "styczeń",
        2: "luty",
        3: "marzec",
        4: "kwiecień",
        5: "maj",
        6: "czerwiec",
        7: "lipiec",
        8: "sierpień",
        9: "wrzesień",
        10: "październik",
        11: "listopad",
        12: "grudzień",
    }
    return names[month]


def get_weather_context(lat: float, lon: float, analysis_date: date) -> Dict:
    today = date.today()
    archive_end = min(analysis_date, today - timedelta(days=5))
    archive_start = _ten_years_back(archive_end)

    archive = fetch_json(
        ARCHIVE_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": archive_start.isoformat(),
            "end_date": archive_end.isoformat(),
            "daily": [
                "precipitation_sum",
                "temperature_2m_mean",
                "temperature_2m_max",
                "et0_fao_evapotranspiration",
            ],
            "timezone": "auto",
        },
        timeout=60,
        cache_ttl_seconds=60 * 60 * 12,
    )
    rows = _iter_weather_rows(archive)

    recent_window_end = archive_end
    recent_window_start = recent_window_end - timedelta(days=29)
    recent_rows = [row for row in rows if recent_window_start <= row["date"] <= recent_window_end]
    historical_same_period = [
        row
        for row in rows
        if row["date"].month == analysis_date.month and abs(row["date"].day - analysis_date.day) <= 15
    ]
    if not historical_same_period:
        historical_same_period = rows[-300:]

    recent_precip = _sum_metric(recent_rows, "precipitation")
    recent_et0 = _sum_metric(recent_rows, "et0")
    recent_temperature_mean = round(
        mean(row["temperature_mean"] for row in recent_rows),
        1,
    ) if recent_rows else None
    recent_balance = round(recent_precip - recent_et0, 2)
    historical_precip_avg = round(mean([row["precipitation"] for row in historical_same_period]), 2)
    historical_et0_avg = round(mean([row["et0"] for row in historical_same_period]), 2)
    historical_precip_window = round(historical_precip_avg * max(len(recent_rows), 1), 2)

    monthly = defaultdict(lambda: {"precipitation": 0.0, "et0": 0.0, "count": 0})
    yearly_dry_days = defaultdict(int)
    yearly_total_days = defaultdict(int)
    for row in rows:
        month_bucket = monthly[row["date"].month]
        month_bucket["precipitation"] += row["precipitation"]
        month_bucket["et0"] += row["et0"]
        month_bucket["count"] += 1

        dryness = row["et0"] - row["precipitation"]
        year_key = row["date"].year
        yearly_total_days[year_key] += 1
        if dryness > 1.5:
            yearly_dry_days[year_key] += 1

    month_risks = []
    for month_number, values in monthly.items():
        deficit_ratio = _safe_ratio(values["et0"] - values["precipitation"], max(values["et0"], 1.0))
        month_risks.append((deficit_ratio, month_number))
    month_risks.sort(reverse=True)
    high_risk_months = [_month_name(month) for _, month in month_risks[:3]]

    yearly_frequencies = []
    for year_key, total_days in yearly_total_days.items():
        yearly_frequencies.append(_safe_ratio(yearly_dry_days[year_key], max(total_days, 1)))
    drought_frequency = round(mean(yearly_frequencies) * 100, 1) if yearly_frequencies else 0.0

    recent_deficit_ratio = _safe_ratio(recent_et0 - recent_precip, max(recent_et0, 1.0))
    anomaly_ratio = _safe_ratio(historical_precip_window - recent_precip, max(historical_precip_window, 1.0))

    forecast = None
    if analysis_date >= today - timedelta(days=2):
        forecast_payload = fetch_json(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": ["precipitation_sum", "et0_fao_evapotranspiration", "temperature_2m_max"],
                "forecast_days": 7,
                "timezone": "auto",
            },
            timeout=30,
            cache_ttl_seconds=60 * 60,
        )
        forecast_rows = _iter_weather_rows(forecast_payload)
        forecast = {
            "precipitation_7d_mm": _sum_metric(forecast_rows, "precipitation"),
            "et0_7d_mm": _sum_metric(forecast_rows, "et0"),
            "max_temperature_7d_c": round(max((row["temperature_max"] for row in forecast_rows), default=0.0), 1),
        }

    return {
        "recent_precipitation_mm": recent_precip,
        "recent_et0_mm": recent_et0,
        "recent_temperature_mean_c": recent_temperature_mean,
        "recent_balance_mm": recent_balance,
        "historical_same_period_precip_avg_mm": historical_precip_avg,
        "historical_same_period_et0_avg_mm": historical_et0_avg,
        "recent_deficit_ratio": round(recent_deficit_ratio, 3),
        "precipitation_anomaly_ratio": round(anomaly_ratio, 3),
        "drought_frequency_pct": drought_frequency,
        "high_risk_months": high_risk_months,
        "forecast": forecast,
    }
