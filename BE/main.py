
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import date, timedelta
from scipy.stats import linregress
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from fastapi.encoders import jsonable_encoder
import hashlib
import json
import time
import numpy as np
import pandas as pd

# Import funkcji kolegi
try:
    from .model import ocen as ocen_model, LimitDzienny
    from . import rekomendacje
    from .raport import zbuduj_pdf
    from .services.data_sources.weather import get_weather_context
    from .services.data_sources.http import CACHE_ROOT, _load_cached, write_cached
    from .services.data_sources.parcel import (
        ParcelServiceError,
        geocode_address,
        lookup_parcel_by_id,
        lookup_parcel_by_id_or_nr,
        lookup_parcel_by_point,
        reverse_geocode,
    )
except ImportError:
    from model import ocen as ocen_model, LimitDzienny
    import rekomendacje
    from raport import zbuduj_pdf
    from services.data_sources.weather import get_weather_context
    from services.data_sources.http import CACHE_ROOT, _load_cached, write_cached
    from services.data_sources.parcel import (
        ParcelServiceError,
        geocode_address,
        lookup_parcel_by_id,
        lookup_parcel_by_id_or_nr,
        lookup_parcel_by_point,
        reverse_geocode,
    )


# ==================================================
# KONFIGURACJA
# ==================================================

app = FastAPI(
    title="Soil Moisture AI API",
    description="API do oceny wilgotności gleby w Polsce",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Na produkcji ustaw domenę frontendu
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ==================================================
# MODEL DANYCH WEJŚCIOWYCH
# ==================================================

UPRAWY = rekomendacje.UPRAWY


class OcenaInput(BaseModel):
    lat: float = Field(ge=49.0, le=55.0)
    lon: float = Field(ge=14.0, le=25.0)
    data_analizy: date
    uprawa: Optional[str] = None


# ==================================================
# CACHE WYNIKÓW OCENY (BE/.cache/ocena, max 5 rekordów, TTL 4 h)
# Ten sam mechanizm co BE/.cache/http: plik <sha256>.json, ważność wg mtime.
# ==================================================

OCENA_CACHE_DIR = CACHE_ROOT / "ocena"
OCENA_CACHE_MAX = 5
OCENA_CACHE_TTL_S = 4 * 60 * 60


def _plik_cache(dane: "OcenaInput") -> Path:
    # Zaokrąglenie do 4 miejsc (~11 m), żeby drobne różnice współrzędnych trafiały w ten sam wpis
    klucz = [round(dane.lat, 4), round(dane.lon, 4), dane.data_analizy.isoformat(), dane.uprawa or None]
    return OCENA_CACHE_DIR / f"{hashlib.sha256(json.dumps(klucz).encode()).hexdigest()}.json"


def _cache_get(plik: Path) -> Optional[dict]:
    try:
        tekst = _load_cached(plik, OCENA_CACHE_TTL_S)
        if tekst is None:
            plik.unlink(missing_ok=True)   # przeterminowany wpis nie zajmuje miejsca w limicie
            return None
        return json.loads(tekst)
    except (OSError, ValueError):
        plik.unlink(missing_ok=True)
        return None


def _cache_set(plik: Path, wartosc: dict) -> None:
    try:
        write_cached(plik, json.dumps(jsonable_encoder(wartosc)))
    except (TypeError, ValueError):
        return   # nieserializowalna odpowiedź – po prostu jej nie cache'ujemy
    # Limit rekordów: usuń najstarsze pliki ponad OCENA_CACHE_MAX
    try:
        pliki = sorted(OCENA_CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for stary in pliki[OCENA_CACHE_MAX:]:
        stary.unlink(missing_ok=True)


def _pogoda_dla_ui(lat: float, lon: float, data_analizy: date) -> Optional[dict]:
    try:
        context = get_weather_context(lat, lon, data_analizy)
    except Exception:
        return None

    forecast = context.get("forecast") or {}
    temperature = context.get("recent_temperature_mean_c")
    if temperature is None:
        temperature = forecast.get("max_temperature_7d_c")

    return {
        "temperatura_srednia_c": temperature,
        "opady_30_dni_mm": context.get("recent_precipitation_mm"),
        "wilgotnosc_gleby_pct": None,
        "forecast": forecast,
    }


def _ocena_dla_ui(wynik: dict, szereg_czasowy: list[dict], uprawa: Optional[str], dzien: date) -> dict:
    """Łańcuch: KROK 1 ocena AI -> KROK 2 sugestia dla uprawy -> KROK 3 rekomendacje (rekomendacje.py)."""
    r = rekomendacje.zbuduj(wynik, szereg_czasowy, uprawa, dzien)
    k1, k2 = r["krok1"], r["krok2"]
    kolor = {"wysokie": "red", "umiarkowane": "olive", "niskie": k1["kolor"], "nadmiar wody": "green"}[k2["ryzyko"]]
    return {
        "status": k1["stan"],
        "summary": k1["opis"],
        "percentyl": round(float(wynik.get("percentyl") or 50), 1),
        "poziom": k2["ryzyko"],
        "kolor": kolor,
        "zakres": r["zakres"],
        "pewnosc": k1["pewnosc"],
        "trend": k1["trend"],
        "zmiana_7d": k1["zmiana_7d"],
        "prognoza_7d": r["prognoza_7d"],
        "sugestia": {k: k2[k] for k in ("title", "detail", "evidence", "ryzyko", "prog", "faza_krytyczna", "uprawa")},
        "srednia_podatnosc": r["srednia_podatnosc"],
        "miesiace_ryzyka": r["miesiace_ryzyka"],
        "causes": r["przyczyny"],
        "rekomendacje_retencyjne": r["retencja"],
        "rekomendacje_agrotechniczne": r["agrotechnika"],
        "recommendations": r["retencja"] + r["agrotechnika"],
        "uprawa": k2["uprawa"],
        "pogoda": wynik.get("pogoda"),
        "pogoda_status": "unavailable" if wynik.get("pogoda") is None else "available",
    }


# ==================================================
# ENDPOINT GŁÓWNY
# ==================================================

@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Soil Moisture AI działa"
    }


# ==================================================
# OCENA WILGOTNOŚCI
# ==================================================

@app.api_route("/ocena", methods=["GET", "POST"])
@app.api_route("/ocena/", methods=["GET", "POST"])
@app.api_route("/api/ocena", methods=["GET", "POST"])
@app.api_route("/api/ocena/", methods=["GET", "POST"])
def ocena(
    dane: Optional[OcenaInput] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    data_analizy: Optional[date] = None,
):
    if dane is None:
        if lat is not None and lon is not None:
            dane = OcenaInput(
                lat=lat,
                lon=lon,
                data_analizy=data_analizy or date.today(),
            )
        else:
            dane = OcenaInput(
                lat=52.2297,
                lon=21.0122,
                data_analizy=data_analizy or date.today(),
            )

    klucz = _plik_cache(dane)
    z_cache = _cache_get(klucz)
    if z_cache is not None:
        return z_cache

    try:
        # Uruchomienie modelu kolegi
        wynik = ocen_model(
            dane.lat,
            dane.lon,
            dane.data_analizy.isoformat()
        )

        # Pobranie szeregu dziennego
        szereg = wynik.pop("_szereg_dzienny")
        szereg_h = wynik.pop("_szereg_godzinowy", None)

        # Przygotowanie danych do JSON
        wykres_czasowy = []

        for data, row in szereg.iterrows():

            def safe_float(value):
                return None if pd.isna(value) else float(value)

            wykres_czasowy.append({
                "data": data.strftime("%Y-%m-%d"),
                "ocena": safe_float(row["ocena"]),
                "q10": safe_float(row["ocena_q10"]),
                "q90": safe_float(row["ocena_q90"]),
                "era5": safe_float(row["era5_percentyl"])
            })

        # Przebieg wybranego dnia (godziny 00–23)
        wykres_godzinowy = []

        def safe_float(value):
            return None if pd.isna(value) else float(value)

        if szereg_h is not None:
            for ts, row in szereg_h.iterrows():
                wykres_godzinowy.append({
                    "godzina": ts.strftime("%H:%M"),
                    "ocena": safe_float(row["ocena"]),
                    "q10": safe_float(row["ocena_q10"]),
                    "q90": safe_float(row["ocena_q90"]),
                    "era5": safe_float(row["era5_percentyl"]),
                })
        dzien_wykresu = szereg.index[-1].strftime("%Y-%m-%d") if len(szereg) else None

        # ==================================================
        # REGRESJA LINIOWA - DIAGNOSTYKA MODELU
        # ==================================================

        porownanie = szereg[
            ["ocena", "era5_percentyl"]
        ].dropna()

        x = porownanie["era5_percentyl"].to_numpy()
        y = porownanie["ocena"].to_numpy()

        regresja = {
            "dostepna": False,
            "r2": None,
            "slope": None,
            "intercept": None,
            "punkty": [],
            "linia": []
        }

        if len(x) >= 2 and np.unique(x).size >= 2:

            wynik_regresji = linregress(x, y)

            regresja = {
                "dostepna": True,
                "r2": round(float(wynik_regresji.rvalue ** 2), 4),
                "slope": float(wynik_regresji.slope),
                "intercept": float(wynik_regresji.intercept),

                "punkty": [
                    {
                        "rzeczywiste": float(a),
                        "przewidziane": float(b)
                    }
                    for a, b in zip(x, y)
                ],

                "linia": [
                    {
                        "x": float(a),
                        "y": float(wynik_regresji.intercept
                                   + wynik_regresji.slope * a)
                    }
                    for a in np.linspace(
                        float(np.min(x)),
                        float(np.max(x)),
                        100
                    )
                ]
            }

        # ==================================================
        # ODPOWIEDŹ API
        # ==================================================

        # Scal: wartości z modelu (ERA5) mają pierwszeństwo, serwis pogodowy uzupełnia braki
        pogoda_model = wynik.get("pogoda") or {}
        pogoda = _pogoda_dla_ui(dane.lat, dane.lon, dane.data_analizy) or {}
        scalona = {**pogoda, **{k: v for k, v in pogoda_model.items() if v is not None}}
        wynik["pogoda"] = scalona or None

        ocena_ai = _ocena_dla_ui(wynik, wykres_czasowy, dane.uprawa, dane.data_analizy)

        odpowiedz = {
            "status": "success",

            "lokalizacja": {
                "lat": dane.lat,
                "lon": dane.lon
            },

            "wynik": wynik,

            "wykresy": {
                "szereg_czasowy": wykres_czasowy,
                "szereg_godzinowy": wykres_godzinowy,
                "dzien_wykresu": dzien_wykresu,
                "regresja": regresja
            },
            "ocena_ai": ocena_ai,
            "rekomendacje": ocena_ai["recommendations"],
        }
        _cache_set(klucz, odpowiedz)
        return odpowiedz

    except HTTPException:
        raise
    except LimitDzienny:
        raise HTTPException(
            status_code=503,
            detail="Przekroczono limit zapytań Open-Meteo (dane pogodowe). Spróbuj za godzinę lub z innej sieci.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd podczas oceny wilgotności: {str(e)}")


# ==================================================
# INFORMACJE O API
# ==================================================

@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "model": "HistGradientBoostingRegressor"
    }


# ==================================================
# WYSZUKIWANIE LOKALIZACJI / DZIAŁEK (ULDK GUGiK + Nominatim)
# ==================================================
#
# Wszystkie trzy endpointy zwracają ten sam kształt:
# { lat, lon, label, parcel: {...} | null, parcel_error: str | null }
# Punkt i adres działają nawet gdy ULDK jest niedostępne (parcel = null).

def _parcel_dla_ui(parcel: dict) -> dict:
    return {
        "id": parcel["id"],
        "numer": parcel.get("parcel_number"),
        "obreb": parcel.get("region"),
        "gmina": parcel.get("commune"),
        "powiat": parcel.get("county"),
        "wojewodztwo": parcel.get("voivodeship"),
        "powierzchnia_ha": parcel.get("area_ha"),
        "geometry": parcel.get("geometry"),
        "centroid": parcel.get("centroid"),
    }


_ULDK_PAUZA_S = 120
_uldk_niedostepne_do = 0.0
_uldk_komunikat = ""


def _sprobuj_dzialke(lat: float, lon: float):
    global _uldk_niedostepne_do, _uldk_komunikat
    if time.monotonic() < _uldk_niedostepne_do:
        return None, _uldk_komunikat
    try:
        return _parcel_dla_ui(lookup_parcel_by_point(lat, lon)), None
    except ParcelServiceError as exc:
        # nie męcz usługi (i użytkownika) przez chwilę
        _uldk_niedostepne_do = time.monotonic() + _ULDK_PAUZA_S
        _uldk_komunikat = str(exc)
        return None, str(exc)
    except ValueError:
        return None, "W tym miejscu nie znaleziono działki ewidencyjnej"
    except Exception as exc:
        return None, f"Usługa działek niedostępna ({exc.__class__.__name__})"


def _w_polsce(lat: float, lon: float) -> None:
    if not (49.0 <= lat <= 55.0 and 14.0 <= lon <= 25.0):
        raise HTTPException(status_code=400, detail="Punkt leży poza obszarem Polski")


def _etykieta_dzialki(parcel: dict) -> str:
    czesci = [f"Dz. {parcel['numer']}" if parcel.get("numer") else None, parcel.get("obreb"), parcel.get("gmina")]
    return ", ".join(c for c in czesci if c)


@app.get("/api/lokalizacja/punkt")
def lokalizacja_punkt(lat: float, lon: float):
    _w_polsce(lat, lon)
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_parcel = pool.submit(_sprobuj_dzialke, lat, lon)
        f_label = pool.submit(reverse_geocode, lat, lon)
        parcel, parcel_error = f_parcel.result()
        label = f_label.result() or f"{lat:.4f}, {lon:.4f}"
    return {"lat": lat, "lon": lon, "label": label, "parcel": parcel, "parcel_error": parcel_error}


@app.get("/api/lokalizacja/adres")
def lokalizacja_adres(q: str):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Podaj adres")
    try:
        punkt = geocode_address(query)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Geokoder niedostępny ({exc.__class__.__name__})")
    _w_polsce(punkt["lat"], punkt["lon"])
    parcel, parcel_error = _sprobuj_dzialke(punkt["lat"], punkt["lon"])
    return {
        "lat": punkt["lat"],
        "lon": punkt["lon"],
        "label": punkt["label"],
        "parcel": parcel,
        "parcel_error": parcel_error,
    }


@app.get("/api/lokalizacja/dzialka")
def lokalizacja_dzialka(id: str):
    parcel_id = id.strip()
    if not parcel_id:
        raise HTTPException(status_code=400, detail="Podaj identyfikator działki")
    try:
        try:
            parcel = _parcel_dla_ui(lookup_parcel_by_id(parcel_id))
        except ValueError:
            # np. "Krzyki 33/1" – nazwa obrębu + numer działki
            parcel = _parcel_dla_ui(lookup_parcel_by_id_or_nr(parcel_id))
    except ParcelServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Nie znaleziono działki. Podaj pełny identyfikator (np. 141201_1.0001.6509) lub obręb i numer (np. Krzyki 33/1)",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Usługa działek niedostępna ({exc.__class__.__name__})")
    lat, lon = parcel["centroid"]["lat"], parcel["centroid"]["lon"]
    return {"lat": lat, "lon": lon, "label": _etykieta_dzialki(parcel), "parcel": parcel, "parcel_error": None}


# ==================================================
# RAPORT PDF
# ==================================================

class RaportInput(OcenaInput):
    lokalizacja_label: Optional[str] = None
    dzialka: Optional[dict] = None


@app.post("/api/raport")
def raport(dane: RaportInput):
    odp = ocena(dane=OcenaInput(lat=dane.lat, lon=dane.lon, data_analizy=dane.data_analizy, uprawa=dane.uprawa))
    try:
        pdf = zbuduj_pdf(
            odp,
            {"label": dane.lokalizacja_label or f"{dane.lat:.4f}, {dane.lon:.4f}", "lat": dane.lat, "lon": dane.lon},
            dane.dzialka,
            odp["ocena_ai"].get("uprawa"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nie udało się wygenerować raportu: {e}")
    nazwa = f"raport_wilgotnosc_{dane.data_analizy.isoformat()}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nazwa}"'})


@app.get("/api/uprawy")
def get_uprawy():
    return [{"key": k, "label": v["label"], "sensitivity": v["sensitivity"]} for k, v in UPRAWY.items()]
