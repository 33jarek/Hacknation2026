# =============================================================================
#  MODEL OCENY STANU WILGOTNOŚCI GLEBY – etap 1 zadania KOWR
#
#  Jak używać:
#    1) Trening (pobiera dane, trenuje, zapisuje model):
#           python model.py
#       Pobieranie można przerwać (Ctrl+C) i wznowić – każdy punkt jest
#       zapisywany na dysk w folderze dane/punkty.
#    2) W aplikacji:
#           from model import ocen
#           wynik = ocen(53.12, 18.01, "2018-07-15")
#
#  W VS Code każdy fragment zaczynający się od "# %%" można uruchomić
#  osobno przyciskiem "Run Cell" (potrzebne rozszerzenie Jupyter).
#
#  Biblioteki:  pip install pandas numpy scikit-learn scipy matplotlib requests pyarrow joblib
# =============================================================================

# %% 1. USTAWIENIA
import json
import time
from datetime import date, timedelta
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
import requests
import sklearn
from matplotlib.path import Path as Wielokat
from scipy.stats import norm

try:
    FOLDER = Path(__file__).parent          # gdy uruchamiasz jako skrypt
except NameError:
    FOLDER = Path.cwd()                     # gdy uruchamiasz komórki w VS Code

DANE = FOLDER / "dane"
PUNKTY_DIR = DANE / "punkty"                # tu trafia każdy pobrany punkt
WYKRESY = FOLDER / "wykresy"
PLIK_MODELU = FOLDER / "model_wilgotnosc.joblib"
for f in (DANE, PUNKTY_DIR, WYKRESY):
    f.mkdir(parents=True, exist_ok=True)

OKRES_START, OKRES_KONIEC = "2015-01-01", "2025-12-31"   # dane treningowe
ROK_TRENING_DO = 2022            # 2016–2022 nauka, 2023–2025 test
N_PUNKTOW = 60                   # ile punktów w Polsce pobrać do treningu
KROK_SIATKI = 0.5                # odstęp siatki punktów w stopniach
SEED = 42

# Uproszczony obrys Polski (lon, lat) – wystarczy do losowania punktów
OBRYS_POLSKI = [
    (14.2, 53.9), (16.0, 54.2), (17.0, 54.7), (18.5, 54.8), (19.6, 54.4),
    (22.8, 54.4), (23.5, 54.0), (23.9, 53.0), (23.2, 52.3), (23.6, 51.6),
    (24.1, 50.9), (23.5, 50.3), (22.6, 49.5), (22.8, 49.1), (22.0, 49.2),
    (20.9, 49.3), (19.8, 49.2), (18.9, 49.5), (18.0, 50.0), (17.0, 50.3),
    (16.4, 50.6), (15.5, 50.8), (14.8, 50.9), (14.6, 51.6), (14.7, 52.1),
    (14.2, 52.8), (14.4, 53.3),
]

OKNA = [7, 30, 60, 90]           # okna czasowe cech (dni wstecz)


# %% 2. POBIERANIE DANYCH
class LimitDzienny(Exception):
    """Open-Meteo odmówił – dzienny limit wyczerpany (spróbuj inna sieć / jutro)."""


_CACHE_API = Path(__file__).resolve().parent / ".cache" / "openmeteo"


def _get(url, params, proby=4):
    """Zapytanie GET z obsługą limitów: przy limicie minutowym czeka i ponawia.
    Odpowiedzi są cache'owane na dysku (dane archiwalne/wysokości się nie zmieniają)."""
    import hashlib
    klucz = hashlib.sha256(json.dumps([url, sorted(params.items())], default=str).encode()).hexdigest()
    plik = _CACHE_API / f"{klucz}.json"
    if plik.exists():
        try:
            return json.loads(plik.read_text())
        except Exception:
            plik.unlink(missing_ok=True)

    for proba in range(proby):
        zapytanie = {k: v for k, v in params.items() if not str(k).startswith("_")}   # "_x" = tylko klucz cache
        r = requests.get(url, params=zapytanie, timeout=120)
        if r.status_code == 200:
            js = r.json()
            try:
                # zapis atomowy: równoległe zapytania nie czytają niedokończonego pliku
                _CACHE_API.mkdir(parents=True, exist_ok=True)
                tmp = plik.with_suffix(f".{time.monotonic_ns()}.tmp")
                tmp.write_text(json.dumps(js))
                tmp.replace(plik)
            except Exception:
                pass
            return js
        tekst = r.text[:300]
        if r.status_code == 429 and ("Daily" in tekst or "Hourly" in tekst):
            # limit dzienny/godzinowy – czekanie nic nie da, zgłoś od razu
            raise LimitDzienny(tekst)
        if r.status_code in (429, 500, 502, 503, 504):
            czekaj = 60 if r.status_code == 429 else 10 * (proba + 1)
            print(f"   HTTP {r.status_code}, czekam {czekaj} s...")
            time.sleep(czekaj)
            continue
        raise RuntimeError(f"HTTP {r.status_code}: {tekst}")
    raise RuntimeError(f"Nie udało się pobrać po {proby} próbach: {url}")


def pobierz_meteo(lat, lon, start, koniec):
    """Dzienne dane z Open-Meteo (ERA5/ERA5-Land): opad, ET0, Tmax i wilgotność gleby."""
    js = _get("https://archive-api.open-meteo.com/v1/archive", {
        "latitude": round(lat, 3), "longitude": round(lon, 3),
        "start_date": start, "end_date": koniec,
        "daily": "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max",
        "hourly": "soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,soil_moisture_28_to_100cm",
        "timezone": "Europe/Warsaw",
    })
    d = pd.DataFrame(js["daily"])
    d["time"] = pd.to_datetime(d["time"])
    d = d.set_index("time")
    d.columns = ["opad", "et0", "tmax"]

    h = pd.DataFrame(js["hourly"])
    h["time"] = pd.to_datetime(h["time"])
    h = h.set_index("time")
    h.columns = ["sm_0_7", "sm_7_28", "sm_28_100"]
    h_raw = h.tail(48).copy()                        # ostatnie 2 doby – do wykresu dnia
    h = h.resample("D").mean()                       # średnia dobowa

    df = d.join(h)
    # wilgotność strefy korzeni 0–100 cm = średnia ważona grubością warstw
    df["sm_0_100"] = 0.07 * df["sm_0_7"] + 0.21 * df["sm_7_28"] + 0.72 * df["sm_28_100"]
    wynik = df[["opad", "et0", "tmax", "sm_0_100"]].copy()
    # godzinowa wilgotność 0–100 cm (do wykresu przebiegu dnia)
    wynik.attrs["sm_godzinowe"] = 0.07 * h_raw["sm_0_7"] + 0.21 * h_raw["sm_7_28"] + 0.72 * h_raw["sm_28_100"]
    return wynik


GLEBOKOSCI = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm"]
GRUBOSC_CM = np.array([5, 10, 15, 30, 40])


def pobierz_glebe(lat, lon):
    """SoilGrids: glina, piasek [%], węgiel org. [g/kg] dla 5 warstw do 100 cm.
    Gdy serwis nie działa – zwraca None (model poradzi sobie z brakiem)."""
    params = [("lon", round(lon, 4)), ("lat", round(lat, 4)), ("value", "mean")]
    params += [("property", p) for p in ["clay", "sand", "soc"]]
    params += [("depth", g) for g in GLEBOKOSCI]
    try:
        r = requests.get("https://rest.isric.org/soilgrids/v2.0/properties/query",
                         params=params, timeout=60)
        r.raise_for_status()
        js = r.json()
    except Exception as e:
        print("   SoilGrids niedostępne:", str(e)[:100])
        return None
    wynik = {}
    for warstwa in js["properties"]["layers"]:
        dziel = warstwa["unit_measure"]["d_factor"]
        wart = {d["label"]: d["values"]["mean"] for d in warstwa["depths"]}
        v = np.array([np.nan if wart.get(g) is None else wart[g] for g in GLEBOKOSCI],
                     dtype=float) / dziel
        wynik[warstwa["name"]] = v                   # po d_factor: glina/piasek w %, C org. w g/kg
    return wynik


def pobierz_teren(lat, lon, odl_m=150):
    """Wysokość w punkcie i 4 sąsiadach (±150 m) -> spadek terenu."""
    dlat = odl_m / 111_320
    dlon = odl_m / (111_320 * np.cos(np.radians(lat)))
    lats = [lat, lat + dlat, lat - dlat, lat, lat]
    lons = [lon, lon, lon, lon + dlon, lon - dlon]
    try:
        js = _get("https://api.open-meteo.com/v1/elevation", {
            "latitude": ",".join(f"{x:.5f}" for x in lats),
            "longitude": ",".join(f"{x:.5f}" for x in lons),
        })
    except LimitDzienny:
        raise
    except Exception as e:
        print("   Wysokości niedostępne:", str(e)[:100])
        return {"wysokosc_m": np.nan, "spadek_proc": np.nan, "wzgledna_wys_m": np.nan}
    z = np.array(js["elevation"], dtype=float)
    spadek = np.hypot((z[1] - z[2]) / (2 * odl_m), (z[3] - z[4]) / (2 * odl_m))
    return {
        "wysokosc_m": z[0],
        "spadek_proc": 100 * spadek,
        "wzgledna_wys_m": z[0] - z[1:].mean(),   # >0 wzniesienie, <0 obniżenie
    }


# %% 3. CECHY I CEL
def _z_wzgledem_pory_roku(s, okno=15):
    """Odchylenie od normy dla tej samej pory roku (±okno dni) w całym szeregu,
    w jednostkach odchylenia standardowego. Uproszczony odpowiednik SPI/SPEI."""
    doy, v = s.index.dayofyear.values, s.values.astype(float)
    wynik = np.full(len(v), np.nan)
    for d in np.unique(doy):
        odl = np.abs(doy - d)
        odl = np.minimum(odl, 366 - odl)
        pula = v[(odl <= okno) & ~np.isnan(v)]
        if len(pula) > 10 and pula.std() > 0:
            wynik[doy == d] = (v[doy == d] - pula.mean()) / pula.std()
    return pd.Series(wynik, index=s.index)


def cechy_pogodowe(m):
    """Cechy dla każdego dnia – liczone WYŁĄCZNIE z danych z tego dnia i wcześniejszych."""
    bilans = m["opad"] - m["et0"]
    c = pd.DataFrame(index=m.index)
    for n in OKNA:
        c[f"opad_{n}"] = m["opad"].rolling(n, min_periods=n).sum()
        c[f"et0_{n}"] = m["et0"].rolling(n, min_periods=n).sum()
        c[f"bilans_{n}"] = bilans.rolling(n, min_periods=n).sum()
    for n in (30, 60, 90):
        c[f"bilans_{n}_z"] = _z_wzgledem_pory_roku(c[f"bilans_{n}"])
    c["tmax_14"] = m["tmax"].rolling(14, min_periods=14).mean()

    # liczba dni od ostatniego opadu >= 5 mm
    grupa = (m["opad"] >= 5).cumsum()
    c["dni_bez_opadu"] = m.groupby(grupa).cumcount()

    doy = c.index.dayofyear
    c["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    c["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return c


def cechy_gleby_i_terenu(gleba, teren):
    """Cechy stałe dla miejsca. Pojemność wodna wg Saxton & Rawls (2006)."""
    c = dict(teren)
    if gleba is None:
        c.update(glina_0_30=np.nan, piasek_0_30=np.nan, c_org_0_30=np.nan,
                 pojemnosc_wodna_mm=np.nan)
        return c
    w = GRUBOSC_CM[:3] / GRUBOSC_CM[:3].sum()
    c["glina_0_30"] = float(np.nansum(gleba["clay"][:3] * w))
    c["piasek_0_30"] = float(np.nansum(gleba["sand"][:3] * w))
    c["c_org_0_30"] = float(np.nansum(gleba["soc"][:3] * w))

    S, C = gleba["sand"] / 100, gleba["clay"] / 100
    OM = gleba["soc"] / 10 * 1.724                      # g/kg C -> % materii org.
    t1500 = -0.024*S + 0.487*C + 0.006*OM + 0.005*S*OM - 0.013*C*OM + 0.068*S*C + 0.031
    th1500 = t1500 + (0.14 * t1500 - 0.02)              # punkt więdnięcia
    t33 = -0.251*S + 0.195*C + 0.011*OM + 0.006*S*OM - 0.027*C*OM + 0.452*S*C + 0.299
    th33 = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)  # polowa pojemność wodna
    mm = np.clip(th33 - th1500, 0, None) * GRUBOSC_CM * 10
    c["pojemnosc_wodna_mm"] = float(np.nansum(mm)) if np.isfinite(mm).any() else np.nan
    return c


def percentyl_wilgotnosci(sm, okno=7):
    """CEL MODELU: jak wilgotność danego dnia wypada na tle tej samej pory roku
    (±7 dni) we wszystkich latach szeregu. 0 = najsuchszy, 100 = najwilgotniejszy."""
    doy, v = sm.index.dayofyear.values, sm.values.astype(float)
    wynik = np.full(len(v), np.nan)
    for d in np.unique(doy):
        odl = np.abs(doy - d)
        odl = np.minimum(odl, 366 - odl)
        pula = v[(odl <= okno) & ~np.isnan(v)]
        if len(pula) >= 30:
            idx = np.where(doy == d)[0]
            wynik[idx] = (pula[None, :] < v[idx, None]).mean(axis=1) * 100
    wynik[np.isnan(v)] = np.nan
    return pd.Series(wynik, index=sm.index)


def klasa(p):
    if p is None or np.isnan(p):
        return "brak danych"
    if p < 10:
        return "silny niedobór"
    if p < 30:
        return "niedobór"
    if p <= 70:
        return "norma"
    return "wilgotno"


CECHY = (
    [f"{x}_{n}" for x in ("opad", "et0", "bilans") for n in OKNA]
    + ["bilans_30_z", "bilans_60_z", "bilans_90_z", "tmax_14", "dni_bez_opadu",
       "doy_sin", "doy_cos",
       "glina_0_30", "piasek_0_30", "c_org_0_30", "pojemnosc_wodna_mm",
       "wysokosc_m", "spadek_proc", "wzgledna_wys_m"]
)


# Model v2: oprócz pogody/gleby/terenu zna ostatni znany stan wilgotności (ERA5) sprzed 7/14/28 dni.
# Dzięki temu uczy się DYNAMIKI: jak pogoda z ostatniego tygodnia zmienia stan gleby.
# Ten sam model zasilony prognozą pogody daje prognozę stanu na +7 dni.
STANY = ["stan_lag7", "stan_lag14", "stan_lag28"]
CECHY_V2 = CECHY + STANY


def dodaj_stany(df):
    """Dla zbioru treningowego (wiersze co 7 dni): percentyl z dnia d-7/-14/-28 tego samego punktu."""
    df = df.sort_values(["lat", "lon", "data"]).reset_index(drop=True)
    for dni, kol in zip((7, 14, 28), STANY):
        czesci = []
        for _, grp in df.groupby(["lat", "lon"], sort=False):
            src = grp[["data", "cel"]].rename(columns={"data": "d_src", "cel": "v"}).sort_values("d_src")
            q = pd.DataFrame({"d": grp["data"] - pd.Timedelta(days=dni), "i": grp.index})
            m = pd.merge_asof(q.sort_values("d"), src, left_on="d", right_on="d_src",
                              direction="nearest", tolerance=pd.Timedelta(days=3))
            czesci.append(m.set_index("i")["v"])
        df[kol] = pd.concat(czesci).reindex(df.index)
    return df


# %% 4. BUDOWA ZBIORU TRENINGOWEGO
def losuj_punkty(n=N_PUNKTOW, krok=KROK_SIATKI, seed=SEED):
    """Siatka punktów w obrysie Polski, z której losujemy n (pokrycie całego kraju)."""
    obrys = Wielokat(OBRYS_POLSKI)
    siatka = [(round(lat, 3), round(lon, 3))
              for lon in np.arange(14.3, 24.1, krok)
              for lat in np.arange(49.2, 54.8, krok)
              if obrys.contains_point((lon, lat))]
    rng = np.random.default_rng(seed)
    wybor = rng.choice(len(siatka), size=min(n, len(siatka)), replace=False)
    return [siatka[i] for i in sorted(wybor)]


def dane_punktu(lat, lon):
    """Pobiera (lub wczytuje z dysku) dane jednego punktu i liczy cechy + cel."""
    plik = PUNKTY_DIR / f"{lat:.3f}_{lon:.3f}.parquet"
    if plik.exists():
        return pd.read_parquet(plik)

    meteo = pobierz_meteo(lat, lon, OKRES_START, OKRES_KONIEC)
    stale = cechy_gleby_i_terenu(pobierz_glebe(lat, lon), pobierz_teren(lat, lon))

    df = cechy_pogodowe(meteo)
    df["cel"] = percentyl_wilgotnosci(meteo["sm_0_100"])
    for k, v in stale.items():
        df[k] = v
    df["lat"], df["lon"] = lat, lon

    # próbka: co 7 dni w sezonie III–X, od 2016 (2015 to rozbieg dla okien 90 dni)
    df = df[(df.index.year >= 2016) & df.index.month.isin(range(3, 11))]
    df = df.iloc[::7].dropna(subset=["cel"])
    df.index.name = "data"
    df = df.reset_index()
    df.to_parquet(plik)
    time.sleep(12)                    # SoilGrids: ok. 5 zapytań na minutę
    return df


def zbuduj_zbior():
    punkty = losuj_punkty()
    print(f"Punktów do pobrania: {len(punkty)}")
    czesci = []
    for i, (lat, lon) in enumerate(punkty, 1):
        try:
            czesci.append(dane_punktu(lat, lon))
            print(f"[{i}/{len(punkty)}] {lat}, {lon} OK")
        except LimitDzienny as e:
            print(f"\nLIMIT DZIENNY Open-Meteo: {e}\n"
                  "Zmień sieć (hotspot) albo uruchom ponownie jutro – pobrane punkty są zapisane.")
            break
        except Exception as e:
            print(f"[{i}/{len(punkty)}] {lat}, {lon} BŁĄD: {str(e)[:150]}")
    if not czesci:
        raise SystemExit("Brak danych do treningu.")
    df = pd.concat(czesci, ignore_index=True)
    df["data"] = pd.to_datetime(df["data"])
    df.to_parquet(DANE / "train.parquet")
    print(f"\nZbiór: {len(df)} wierszy z {df[['lat', 'lon']].drop_duplicates().shape[0]} punktów")
    return df


# %% 5. TRENING I PORÓWNANIE MODELI
def trenuj(df):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    df = dodaj_stany(df).dropna(subset=["stan_lag7"])

    # Podział PO LATACH: model sprawdzamy na latach, których nie widział
    rok = df["data"].dt.year
    tr, te = df[rok <= ROK_TRENING_DO], df[rok > ROK_TRENING_DO]
    Xtr, ytr, Xte, yte = tr[CECHY_V2], tr["cel"], te[CECHY_V2], te["cel"]
    print(f"Trening: {len(tr)} wierszy (do {ROK_TRENING_DO}), test: {len(te)} wierszy")

    def gb(**k):
        return HistGradientBoostingRegressor(max_iter=600, learning_rate=0.03, min_samples_leaf=60,
                                             l2_regularization=1.0, max_leaf_nodes=15,
                                             random_state=SEED, **k)

    modele = {
        # 0) bez uczenia: "będzie tak jak tydzień temu"
        "persystencja_7d": None,
        # 1) v1: sama pogoda/gleba/teren (bez stanu)
        "v1_bez_stanu": HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, random_state=SEED),
        # 2) regresja liniowa ze stanem
        "ridge": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1.0)),
        # 3) model docelowy
        "gradient_boosting": gb(),
    }

    wyniki, predykcje = {}, {}
    for nazwa, m in modele.items():
        if m is None:
            p = Xte["stan_lag7"].values
        elif nazwa == "v1_bez_stanu":
            m.fit(tr[CECHY], ytr)
            p = np.clip(m.predict(te[CECHY]), 0, 100)
        else:
            m.fit(Xtr, ytr)
            p = np.clip(m.predict(Xte), 0, 100)
        predykcje[nazwa] = p
        wyniki[nazwa] = {
            "MAE": round(float(mean_absolute_error(yte, p)), 2),
            "R2": round(float(r2_score(yte, p)), 3),
            "zgodnosc_klas": round(float(np.mean([klasa(a) == klasa(b) for a, b in zip(p, yte)])), 3),
            "trafnosc_niedoboru": round(float(np.mean((p < 30) == (yte.values < 30))), 3),
            "blad_do_15_pkt": round(float(np.mean(np.abs(p - yte.values) <= 15)), 3),
        }
    print("\nWyniki na latach testowych (MAE = średni błąd w punktach percentyla):")
    print(pd.DataFrame(wyniki).T)

    # Przedział niepewności: modele kwantylowe + kalibracja (conformal) na ostatnim roku treningu,
    # żeby przedział 10–90 faktycznie obejmował ~80% przypadków.
    kal = tr["data"].dt.year == ROK_TRENING_DO
    q10k = gb(loss="quantile", quantile=0.1).fit(Xtr[~kal], ytr[~kal])
    q90k = gb(loss="quantile", quantile=0.9).fit(Xtr[~kal], ytr[~kal])
    E = np.maximum(q10k.predict(Xtr[kal]) - ytr[kal], ytr[kal] - q90k.predict(Xtr[kal]))
    margines = float(np.quantile(E, 0.8))
    q10 = gb(loss="quantile", quantile=0.1).fit(Xtr, ytr)
    q90 = gb(loss="quantile", quantile=0.9).fit(Xtr, ytr)
    lo, hi = q10.predict(Xte) - margines, q90.predict(Xte) + margines
    pokrycie = float(np.mean((yte >= lo) & (yte <= hi)))
    print(f"\nPrzedział 10–90 (+{margines:.1f} pkt kalibracji): pokrycie {pokrycie:.0%} (cel ok. 80%), "
          f"śr. szerokość {np.mean(np.clip(hi,0,100) - np.clip(lo,0,100)):.1f}")
    wyniki["przedzial_10_90"] = {"pokrycie": round(pokrycie, 3), "margines": round(margines, 2)}
    q10.margines_ = -margines
    q90.margines_ = margines

    return modele, q10, q90, wyniki, te, predykcje


# %% 6. OCENA: GDZIE MODEL SIĘ MYLI, KTÓRE CECHY SĄ WAŻNE
def ocen_model(model, te, predykcje):
    import matplotlib.pyplot as plt
    from sklearn.inspection import permutation_importance

    te = te.copy()
    te["pred"] = predykcje["gradient_boosting"]
    te["blad"] = (te["pred"] - te["cel"]).abs()

    print("\nŚredni błąd wg roku:")
    print(te.groupby(te["data"].dt.year)["blad"].mean().round(1))

    te["gleba"] = pd.cut(te["piasek_0_30"], [0, 40, 65, 100], labels=["ciężka", "średnia", "lekka"])
    print("\nŚredni błąd wg gleby:")
    print(te.groupby("gleba", observed=True)["blad"].mean().round(1))

    probka = te.sample(min(3000, len(te)), random_state=SEED)
    imp = permutation_importance(model, probka[CECHY_V2], probka["cel"], n_repeats=5,
                                 random_state=SEED, scoring="neg_mean_absolute_error")
    waznosc = pd.Series(imp.importances_mean, index=CECHY_V2).sort_values(ascending=False)
    print("\nNajważniejsze cechy (o ile rośnie błąd po ich 'zepsuciu'):")
    print(waznosc.head(10).round(2))

    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    ax[0].scatter(te["cel"], te["pred"], s=3, alpha=0.3)
    ax[0].plot([0, 100], [0, 100], "k--")
    ax[0].set_xlabel("prawdziwy percentyl (ERA5-Land)")
    ax[0].set_ylabel("przewidziany percentyl")
    ax[0].set_title("Lata testowe")
    waznosc.head(10)[::-1].plot.barh(ax=ax[1])
    ax[1].set_title("Ważność cech")
    plt.tight_layout()
    plt.savefig(WYKRESY / "ocena_modelu.png", dpi=120)
    plt.close()
    print(f"\nWykres zapisany: {WYKRESY / 'ocena_modelu.png'}")
    return waznosc


# %% 7. ZAPIS MODELU
def zapisz(model, q10, q90, wyniki, waznosc, df):
    paczka = {
        "model": model, "q10": q10, "q90": q90, "cechy": CECHY_V2, "wersja_modelu": 2,
        "wersja_sklearn": sklearn.__version__,
        "trening": {"okres": [OKRES_START, OKRES_KONIEC], "rok_podzialu": ROK_TRENING_DO,
                    "wierszy": len(df),
                    "punktow": int(df[["lat", "lon"]].drop_duplicates().shape[0]),
                    "utworzono": date.today().isoformat()},
        "wyniki_testu": wyniki,
        "waznosc_cech": waznosc.round(3).to_dict(),
    }
    joblib.dump(paczka, PLIK_MODELU)
    meta = {k: v for k, v in paczka.items() if k not in ("model", "q10", "q90")}
    (FOLDER / "model_wilgotnosc_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nZapisano model: {PLIK_MODELU}")


# %% 8. FUNKCJA DLA APLIKACJI: ocena dla miejsca i daty
_MODEL = None


def ocen(lat, lon, data_analizy):
    """Ocena stanu wilgotności dla punktu i daty + podatność z 10 lat.
    Używa wyłącznie danych z dni <= data_analizy."""
    global _MODEL
    if _MODEL is None:
        _MODEL = joblib.load(PLIK_MODELU)
    pk = _MODEL

    D = pd.Timestamp(data_analizy)
    ostatni_dostepny = pd.Timestamp(date.today() - timedelta(days=6))   # ERA5: ~5 dni opóźnienia
    koniec = min(D, ostatni_dostepny)
    start = koniec - pd.DateOffset(years=10) - pd.Timedelta(days=120)    # 10 lat + rozbieg

    meteo = pobierz_meteo(lat, lon, start.strftime("%Y-%m-%d"), koniec.strftime("%Y-%m-%d"))
    stale = cechy_gleby_i_terenu(pobierz_glebe(lat, lon), pobierz_teren(lat, lon))

    c = cechy_pogodowe(meteo)
    for k, v in stale.items():
        c[k] = v
    c = c[c.index >= start + pd.Timedelta(days=120)]                    # bez rozbiegu

    era5 = percentyl_wilgotnosci(meteo["sm_0_100"])
    c["era5_percentyl"] = era5.reindex(c.index)
    for dni, kol in zip((7, 14, 28), STANY):                               # ostatni znany stan
        c[kol] = era5.shift(dni, freq="D").reindex(c.index)

    # model ocenia KAŻDY dzień z 10 lat naraz
    X = c[pk["cechy"]]
    c["ocena"], c["ocena_q10"], c["ocena_q90"] = _przewiduj(pk, X)

    dzis = c.iloc[-1]
    prognoza = _prognoza_7d(lat, lon, meteo, stale, era5, koniec, pk)
    szereg_godzinowy = _szereg_godzinowy(meteo, koniec, dzis)
    braki = []
    if koniec < D:
        braki.append(f"Dane meteo dostępne do {koniec.date()} (opóźnienie ERA5 ok. 5 dni).")
    if np.isnan(stale.get("pojemnosc_wodna_mm", np.nan)):
        braki.append("Brak danych glebowych (SoilGrids) – ocena mniej pewna.")

    # przyczyny – wartości, które najbardziej odbiegają od normy
    przyczyny = [
        f"bilans wodny 60 dni: {dzis['bilans_60']:.0f} mm "
        f"({'poniżej' if dzis['bilans_60_z'] < 0 else 'powyżej'} normy, z = {dzis['bilans_60_z']:.1f})",
        f"opad z 30 dni: {dzis['opad_30']:.0f} mm",
        f"dni od ostatniego opadu ≥5 mm: {int(dzis['dni_bez_opadu'])}",
    ]
    if not np.isnan(stale.get("pojemnosc_wodna_mm", np.nan)):
        przyczyny.append(f"pojemność wodna gleby 0–100 cm: {stale['pojemnosc_wodna_mm']:.0f} mm, "
                         f"piasek {stale['piasek_0_30']:.0f}%")

    # podatność: w ilu latach w danym miesiącu przeważał niedobór (ocena < 30)
    sez = c[c.index.month.isin([4, 5, 6, 7, 8, 9])]
    mies = sez.groupby([sez.index.year, sez.index.month])["ocena"].mean().unstack()
    podatnosc = (mies < 30).mean().round(2)
    nazwy = {4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX"}

    return {
        "data_analizy": str(D.date()),
        "dzien_ocenionych_danych": str(c.index[-1].date()),
        "percentyl": round(float(dzis["ocena"]), 1),
        "przedzial_10_90": [round(float(dzis["ocena_q10"]), 1), round(float(dzis["ocena_q90"]), 1)],
        "klasa": klasa(dzis["ocena"]),
        "pogoda": {
            "temperatura_srednia_c": round(float(dzis["tmax_14"]), 1) if np.isfinite(dzis["tmax_14"]) else None,
            "opady_30_dni_mm": round(float(dzis["opad_30"]), 1) if np.isfinite(dzis["opad_30"]) else None,
            "wilgotnosc_gleby_pct": round(float(meteo["sm_0_100"].iloc[-1] * 100), 1)
                if np.isfinite(meteo["sm_0_100"].iloc[-1]) else None,
        },
        # surowe cechy dnia + stałe cechy miejsca – wejście dla silnika rekomendacji
        "cechy": {
            **{k: _liczba(dzis.get(k)) for k in (
                "opad_7", "opad_30", "et0_30", "bilans_30", "bilans_60", "bilans_30_z",
                "bilans_60_z", "bilans_90_z", "tmax_14", "dni_bez_opadu")},
            **{k: _liczba(stale.get(k)) for k in (
                "glina_0_30", "piasek_0_30", "c_org_0_30", "pojemnosc_wodna_mm",
                "wysokosc_m", "spadek_proc", "wzgledna_wys_m")},
        },
        "kontrola_era5_percentyl": None if np.isnan(dzis["era5_percentyl"])
                                   else round(float(dzis["era5_percentyl"]), 1),
        "przyczyny": przyczyny,
        "podatnosc_odsetek_lat_z_niedoborem": {nazwy[m]: float(v) for m, v in podatnosc.items()},
        "braki_i_ograniczenia": braki,
        "zrodla": ["Open-Meteo / ERA5, ERA5-Land (CC BY 4.0)", "ISRIC SoilGrids v2.0 (CC BY 4.0)",
                   "Open-Meteo Elevation / Copernicus DEM"],
        "_szereg_dzienny": c[["ocena", "ocena_q10", "ocena_q90", "era5_percentyl"]],
        "_szereg_godzinowy": szereg_godzinowy,
        "prognoza_7d": prognoza,
    }


def _przewiduj(pk, X):
    """Predykcja + skalibrowany przedział 10–90."""
    p = np.clip(pk["model"].predict(X), 0, 100)
    lo = np.clip(pk["q10"].predict(X) + getattr(pk["q10"], "margines_", 0.0), 0, 100)
    hi = np.clip(pk["q90"].predict(X) + getattr(pk["q90"], "margines_", 0.0), 0, 100)
    return p, np.minimum(lo, p), np.maximum(hi, p)


def pobierz_pogode_dni(lat, lon, od, do):
    """Dzienna pogoda (opad, ET0, Tmax) dla dni od..do. Z archiwum ERA5, a gdy jeszcze go nie ma –
    z modelu prognostycznego Open-Meteo (obserwacje z ostatnich dni + prognoza do 16 dni)."""
    od, do = pd.Timestamp(od), pd.Timestamp(do)
    ostatni_archiwum = pd.Timestamp(date.today() - timedelta(days=6))
    daily = "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max"
    if do <= ostatni_archiwum:
        js = _get("https://archive-api.open-meteo.com/v1/archive", {
            "latitude": round(lat, 3), "longitude": round(lon, 3),
            "start_date": od.strftime("%Y-%m-%d"), "end_date": do.strftime("%Y-%m-%d"),
            "daily": daily, "timezone": "Europe/Warsaw"})
        zrodlo = "obserwacje"
    else:
        dzis = pd.Timestamp(date.today())
        if od < dzis - pd.Timedelta(days=90) or do > dzis + pd.Timedelta(days=15):
            return None, None
        js = _get("https://api.open-meteo.com/v1/forecast", {
            "latitude": round(lat, 3), "longitude": round(lon, 3),
            "past_days": 92, "forecast_days": 16,
            "daily": daily, "timezone": "Europe/Warsaw",
            "_dzien": dzis.strftime("%Y-%m-%d")})            # klucz cache: prognoza ważna 1 dzień
        zrodlo = "prognoza pogody" if do > dzis else "obserwacje"
    d = pd.DataFrame(js["daily"])
    d["time"] = pd.to_datetime(d["time"])
    d = d.set_index("time")
    d.columns = ["opad", "et0", "tmax"]
    d = d.loc[od:do]
    if len(d) < (do - od).days + 1 or d.isna().any().any():
        return None, None
    return d, zrodlo


def _prognoza_7d(lat, lon, meteo, stale, era5, koniec, pk):
    """Stan za 7 dni: znany stan na dziś + pogoda z kolejnych 7 dni -> model."""
    koniec = pd.Timestamp(koniec)
    cel = koniec + pd.Timedelta(days=7)
    try:
        pogoda, zrodlo = pobierz_pogode_dni(lat, lon, koniec + pd.Timedelta(days=1), cel)
    except Exception as e:                      # prognoza jest dodatkiem – nie blokuje oceny
        print("   Prognoza 7 dni niedostępna:", str(e)[:100])
        return None
    if pogoda is None:
        return None
    m = pd.concat([meteo[["opad", "et0", "tmax"]], pogoda])
    m = m[~m.index.duplicated(keep="first")]
    c = cechy_pogodowe(m).loc[[cel]]
    for k, v in stale.items():
        c[k] = v
    for dni, kol in zip((7, 14, 28), STANY):
        c[kol] = era5.get(cel - pd.Timedelta(days=dni), np.nan)
    p, lo, hi = _przewiduj(pk, c[pk["cechy"]])
    return {
        "data": str(cel.date()),
        "ocena": round(float(p[0]), 1),
        "q10": round(float(lo[0]), 1),
        "q90": round(float(hi[0]), 1),
        "zrodlo_pogody": zrodlo,
        "opad_7_mm": round(float(pogoda["opad"].sum()), 1),
    }


def _liczba(v):
    """float gotowy do JSON (NaN/None -> None)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, 2) if np.isfinite(v) else None


def _szereg_godzinowy(meteo, dzien, dzis, okno=7):
    """Przebieg wybranego dnia godzina po godzinie: godzinowa wilgotność ERA5 0–100 cm
    jako percentyl na tle tej samej pory roku (±7 dni, wartości dobowe z 10 lat)
    + dzienna ocena modelu i przedział Q10–Q90 (model jest dobowy)."""
    kolumny = ["era5_percentyl", "ocena", "ocena_q10", "ocena_q90"]
    sm_h = meteo.attrs.get("sm_godzinowe")
    if sm_h is None:
        return pd.DataFrame(columns=kolumny)
    dzien = pd.Timestamp(dzien).normalize()
    godziny = sm_h[(sm_h.index >= dzien) & (sm_h.index < dzien + pd.Timedelta(days=1))]

    sm_d = meteo["sm_0_100"].dropna()
    doy = sm_d.index.dayofyear.values
    odl = np.abs(doy - dzien.dayofyear)
    odl = np.minimum(odl, 366 - odl)
    pula = sm_d.values[odl <= okno]

    df = pd.DataFrame(index=godziny.index)
    if len(pula) >= 30:
        v = godziny.values.astype(float)
        perc = (pula[None, :] < v[:, None]).mean(axis=1) * 100
        perc[np.isnan(v)] = np.nan
        df["era5_percentyl"] = perc
    else:
        df["era5_percentyl"] = np.nan
    df["ocena"] = float(dzis["ocena"])
    df["ocena_q10"] = float(dzis["ocena_q10"])
    df["ocena_q90"] = float(dzis["ocena_q90"])
    return df


# %% 9. URUCHOMIENIE TRENINGU (tylko gdy: python model.py)
if __name__ == "__main__":
    import sys
    matplotlib.use("Agg")                 # wykresy do plików, bez okienek
    if len(sys.argv) > 1:                 # python model.py dane/train.parquet  -> bez pobierania
        df = pd.read_parquet(sys.argv[1])
        df["data"] = pd.to_datetime(df["data"])
    else:
        df = zbuduj_zbior()
    modele, q10, q90, wyniki, te, predykcje = trenuj(df)
    waznosc = ocen_model(modele["gradient_boosting"], te, predykcje)
    zapisz(modele["gradient_boosting"], q10, q90, wyniki, waznosc, df)

    print("\nTest funkcji ocen() dla okolic Bydgoszczy, 15.07.2018:")
    try:
        w = ocen(53.12, 18.01, "2018-07-15")
        w.pop("_szereg_dzienny")
        w.pop("_szereg_godzinowy", None)
        print(json.dumps(w, indent=2, ensure_ascii=False, default=str))
    except LimitDzienny:
        print("Limit Open-Meteo – test ocen() pominięty.")