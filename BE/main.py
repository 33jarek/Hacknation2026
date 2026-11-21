
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import date
from scipy.stats import linregress
import numpy as np
import pandas as pd

# Import funkcji kolegi
from model import ocen as ocen_model


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

class OcenaInput(BaseModel):
    lat: float = Field(ge=49.0, le=55.0)
    lon: float = Field(ge=14.0, le=25.0)
    data_analizy: date


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

@app.post("/ocena")
def ocena(dane: OcenaInput):

    try:
        # Uruchomienie modelu kolegi
        wynik = ocen_model(
            dane.lat,
            dane.lon,
            dane.data_analizy.isoformat()
        )

        # Pobranie szeregu dziennego
        szereg = wynik.pop("_szereg_dzienny")

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

        return {
            "status": "success",

            "lokalizacja": {
                "lat": dane.lat,
                "lon": dane.lon
            },

            "wynik": wynik,

            "wykresy": {
                "szereg_czasowy": wykres_czasowy,
                "regresja": regresja
            }
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Błąd podczas oceny wilgotności: {str(e)}"
        )


# ==================================================
# INFORMACJE O API
# ==================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model": "HistGradientBoostingRegressor"
    }
