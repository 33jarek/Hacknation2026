from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory

from backend.services.data_sources.http import safe_call
from backend.services.data_sources.hydro import get_hydro_context
from backend.services.data_sources.parcel import lookup_parcel_by_address, lookup_parcel_by_id, lookup_parcel_by_point
from backend.services.data_sources.satellite import get_satellite_context
from backend.services.data_sources.soil import get_soil_context
from backend.services.data_sources.terrain import get_terrain_context
from backend.services.data_sources.weather import get_weather_context
from backend.services.report.build_report import build_report
from backend.services.scoring.analysis import summarize_analysis
from backend.services.scoring.recommendations import build_recommendations

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")


def _bad_request(message: str, status: int = 400):
    response = jsonify({"error": message})
    response.status_code = status
    return response


def _parse_analysis_date(raw_value: Optional[str]) -> date:
    if not raw_value:
        return date.today()
    return datetime.strptime(raw_value, "%Y-%m-%d").date()


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/parcel/by-id")
def parcel_by_id():
    parcel_id = request.args.get("id", "").strip()
    if not parcel_id:
        return _bad_request("Brak identyfikatora działki")
    parcel, error = safe_call(lookup_parcel_by_id, parcel_id)
    if error:
        return _bad_request(f"Nie udało się znaleźć działki: {error}", 502)
    return jsonify(parcel)


@app.route("/api/parcel/by-address")
def parcel_by_address():
    query = request.args.get("q", "").strip()
    if not query:
        return _bad_request("Brak adresu")
    parcel, error = safe_call(lookup_parcel_by_address, query)
    if error:
        return _bad_request(f"Nie udało się znaleźć działki dla adresu: {error}", 502)
    return jsonify(parcel)


@app.route("/api/parcel/by-point")
def parcel_by_point():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    if not lat or not lon:
        return _bad_request("Brak współrzędnych")
    parcel, error = safe_call(lookup_parcel_by_point, float(lat), float(lon))
    if error:
        return _bad_request(f"Nie udało się znaleźć działki: {error}", 502)
    return jsonify(parcel)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    payload = request.get_json(silent=True) or {}
    parcel_id = (payload.get("parcelId") or "").strip()
    crop = (payload.get("crop") or "").strip()
    if not parcel_id:
        return _bad_request("Brak identyfikatora działki")
    if not crop:
        return _bad_request("Brak uprawy")

    analysis_date = _parse_analysis_date(payload.get("analysisDate"))
    parcel, error = safe_call(lookup_parcel_by_id, parcel_id)
    if error:
        return _bad_request(f"Nie udało się odświeżyć działki: {error}", 502)

    lat = parcel["centroid"]["lat"]
    lon = parcel["centroid"]["lon"]

    signals = {}
    missing_data = []
    adapters = [
        ("weather", get_weather_context, (lat, lon, analysis_date)),
        ("soil", get_soil_context, (lat, lon)),
        ("terrain", get_terrain_context, (lat, lon)),
        ("hydro", get_hydro_context, (lat, lon)),
        ("satellite", get_satellite_context, (parcel["geometry"], parcel["bbox"], analysis_date)),
    ]

    for key, func, args in adapters:
        result, source_error = safe_call(func, *args)
        if source_error:
            missing_data.append(f"{key}: {source_error}")
        else:
            signals[key] = result

    summary = summarize_analysis(parcel, crop, analysis_date.isoformat(), signals, missing_data)
    recommendations = build_recommendations(summary)

    limitations = [
        "Powierzchnia działki jest przybliżona z geometrii WGS84 i ma charakter orientacyjny.",
        "SoilGrids to produkt o małej rozdzielczości i może nie oddawać zróżnicowania w obrębie jednej działki.",
        "Sygnał satelitarny pochodzi z najnowszej dostępnej sceny Landsat i może zależeć od zachmurzenia, daty zobrazowania oraz fazy uprawy.",
        "Kontekst hydrologiczny opiera się na pobliskich obiektach z OpenStreetMap i nie zastępuje oceny rowów, melioracji ani ekspertyzy technicznej.",
        "Ocena korzysta z przejrzystych reguł, a nie ze skalibrowanego bilansu wodnego gospodarstwa.",
    ]
    if analysis_date > date.today():
        limitations.append("Datę przyszłą można wskazać, ale źródła danych sięgają tylko do swojego ostatniego opublikowanego okresu.")

    report = build_report(summary, recommendations, missing_data, limitations)
    return jsonify(report)


@app.route("/<path:path>")
def static_files(path: str):
    target = FRONTEND_DIR / path
    if target.exists():
        return send_from_directory(FRONTEND_DIR, path)
    return _bad_request("Nie znaleziono", 404)
