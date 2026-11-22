
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import date, timedelta
from scipy.stats import linregress
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
import time
import numpy as np
import pandas as pd

# Import funkcji kolegi
try:
    from .model import ocen as ocen_model, LimitDzienny
    from .services.data_sources.weather import get_weather_context
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
    from services.data_sources.weather import get_weather_context
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

UPRAWY = {
    "zboza-ozime":    {"label": "Zboża ozime",           "sensitivity": 0.55},
    "zboza-jare":     {"label": "Zboża jare",             "sensitivity": 0.60},
    "kukurydza":      {"label": "Kukurydza",              "sensitivity": 0.80},
    "rzepak":         {"label": "Rzepak i rzepik",        "sensitivity": 0.68},
    "burak-cukrowy":  {"label": "Burak cukrowy",          "sensitivity": 0.78},
    "ziemniaki":      {"label": "Ziemniaki",              "sensitivity": 0.82},
    "straczkowe":     {"label": "Rośliny strączkowe",     "sensitivity": 0.70},
    "uzytki-zielone": {"label": "Użytki zielone",         "sensitivity": 0.60},
    "drzewa-owocowe": {"label": "Drzewa i krzewy owocowe","sensitivity": 0.72},
}


class OcenaInput(BaseModel):
    lat: float = Field(ge=49.0, le=55.0)
    lon: float = Field(ge=14.0, le=25.0)
    data_analizy: date
    uprawa: Optional[str] = None


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


def _ocena_dla_ui(wynik: dict, szereg_czasowy: list[dict], uprawa: Optional[str] = None) -> dict:
    percentyl = float(wynik.get("percentyl") or 50)
    przedzial = wynik.get("przedzial_10_90")
    if not przedzial and szereg_czasowy:
        ostatni = szereg_czasowy[-1]
        przedzial = [ostatni.get("q10"), ostatni.get("q90")]

    profil = UPRAWY.get(uprawa or "", {"label": None, "sensitivity": 0.65})
    sensitivity = profil["sensitivity"]
    uprawa_label = profil.get("label")

    # Próg niedoboru zależy od wrażliwości uprawy (bardziej wrażliwa = wyższy próg)
    prog_silny    = 30 + sensitivity * 10   # 35–38 dla czułych upraw
    prog_umiarko  = 50 + sensitivity * 5    # 52–54
    prog_dobry    = 65 + sensitivity * 10   # 70–73

    if percentyl < prog_silny:
        status = "Silny niedobór wody"
        poziom = "wysoki"
        kolor = "red"
    elif percentyl < prog_umiarko:
        status = "Umiarkowany niedobór wody"
        poziom = "umiarkowany"
        kolor = "olive"
    elif percentyl < prog_dobry:
        status = "Zrównoważony stan wilgotności"
        poziom = "umiarkowany"
        kolor = "olive"
    else:
        status = "Dobra wilgotność gleby"
        poziom = "niski"
        kolor = "green"

    podatnosc = wynik.get("podatnosc_odsetek_lat_z_niedoborem") or {}
    wartosci = [float(value) for value in podatnosc.values()]
    srednia = round(sum(wartosci) / len(wartosci), 2) if wartosci else None
    wysokie_miesiace = [
        miesiac for miesiac, value in sorted(
            podatnosc.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
    ] if podatnosc else []

    przyczyny = wynik.get("przyczyny") or []
    causes = []
    for pozycja in przyczyny[:3]:
        text = str(pozycja)
        if "bilans" in text.lower():
            causes.append({"title": "Bilans wodny", "value": text, "detail": "Suma opadów i parowania określana na podstawie danych pogodowych."})
        elif "opad" in text.lower():
            causes.append({"title": "Opady", "value": text, "detail": "Krótki okres opadowy wpływa na bieżący stan wilgotności."})
        elif "pojemność" in text.lower():
            causes.append({"title": "Zdolność retencyjna gleby", "value": text, "detail": "Wynik opisuje zdolność profilu glebowego do magazynowania wody."})
        else:
            causes.append({"title": "Czynnik agrometeorologiczny", "value": text, "detail": "Informacja wyliczona przez model wilgotności gleby."})
    if not causes:
        causes = [{
            "title": "Dane klimatyczne",
            "value": f"Percentyl: {percentyl:.1f}",
            "detail": "Ocena oparta na rozkładzie wilgotności gleby z wielolecia.",
        }]

    # Rekomendacje zależne od uprawy i percentylu
    recommendations = []
    irr_threshold = 35 - sensitivity * 5  # wrażliwsze uprawy wymagają wcześniejszego nawadniania

    if percentyl < prog_umiarko:
        recommendations.append({
            "title": "Zwiększ retencję wody na działce",
            "category": "retention",
            "priority": "Pilne",
            "detail": "Zastosuj mulczowanie, resztki pożniwne i elementy spowalniające odpływ, dobierając rozwiązania do ukształtowania terenu.",
            "evidence": f"Percentyl modelu: {percentyl:.1f}" + (f" | Uprawa: {uprawa_label}" if uprawa_label else ""),
        })
    else:
        recommendations.append({
            "title": "Podtrzymuj zdolność retencji pola",
            "category": "retention",
            "priority": "Polecane",
            "detail": "Kontynuuj ochronę struktury gleby i ograniczaj intensywny spływ podczas opadów.",
            "evidence": f"Percentyl modelu: {percentyl:.1f}",
        })

    recommendations.append({
        "title": "Wykonaj zabiegi agrotechniczne chroniące wilgoć",
        "category": "agrotechnical",
        "priority": "Pilne" if percentyl < 40 else "Polecane",
        "detail": "Dobierz termin uprawy, termin i głębokość siewu oraz ochronę resztkami pożniwymi do bieżącego stanu pola."
        + (f" Dla uprawy {uprawa_label} szczególnie ważna jest ciągłość zaopatrzenia w wodę." if uprawa_label else ""),
        "evidence": ", ".join(wysokie_miesiace) if wysokie_miesiace else "Brak danych o miesiącach ryzyka",
    })

    if percentyl < irr_threshold:
        recommendations.append({
            "title": "Przygotuj i rozpocznij nawadnianie",
            "category": "irrigation",
            "priority": "Pilne",
            "detail": "Sprawdź wilgotność w warstwie korzeniowej i zastosuj nawadnianie dawkami dopasowanymi do uprawy oraz przepuszczalności gleby."
            + (f" {uprawa_label} ma wysoką wrażliwość na suszę ({int(sensitivity*100)}%)." if uprawa_label else ""),
            "evidence": f"Przedział modelu (percentyl): {przedzial[0]:.0f}–{przedzial[1]:.0f}"
            if przedzial else "Brak przedziału niepewności",
        })
    else:
        recommendations.append({
            "title": "Monitoruj potrzebę nawadniania",
            "category": "irrigation",
            "priority": "Długoterminowe" if percentyl >= prog_dobry else "Polecane",
            "detail": "Kontroluj wilgotność gleby i opady przed podjęciem decyzji o nawodnieniu; unikaj nawadniania przy zaspokojonej potrzebie uprawy.",
            "evidence": f"Percentyl modelu: {percentyl:.1f}",
        })

    if przedzial:
        zakres = f"{float(przedzial[0]):.0f}–{float(przedzial[1]):.0f}"
    else:
        zakres = "brak przedziału"

    return {
        "status": status,
        "summary": (
            f"Gleba jest wilgotniejsza niż w {percentyl:.0f}% dni o tej porze roku "
            f"z ostatnich 10 lat (50 = typowo)."
            + (f" Progi dopasowane do uprawy: {uprawa_label}." if uprawa_label else "")
        ),
        "percentyl": round(percentyl, 1),
        "poziom": poziom,
        "kolor": kolor,
        "zakres": zakres,
        "srednia_podatnosc": srednia,
        "miesiace_ryzyka": wysokie_miesiace,
        "causes": causes,
        "recommendations": recommendations,
        "uprawa": uprawa_label,
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

        return {
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
            "ocena_ai": _ocena_dla_ui(wynik, wykres_czasowy, dane.uprawa),
            "rekomendacje": _ocena_dla_ui(wynik, wykres_czasowy, dane.uprawa)["recommendations"],
        }

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


@app.get("/api/uprawy")
def get_uprawy():
    return [{"key": k, "label": v["label"], "sensitivity": v["sensitivity"]} for k, v in UPRAWY.items()]
