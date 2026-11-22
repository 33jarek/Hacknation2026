"""Silnik rekomendacji – łańcuch wnioskowania oparty na wyniku modelu AI.

    KROK 1  ocena AI        percentyl + przedział Q10–Q90 + trend 7 dni  ->  stan, pewność
    KROK 2  sugestia        stan z kroku 1 × uprawa (wrażliwość, faza krytyczna)  ->  ryzyko dla uprawy
    KROK 3a retencja        ryzyko z kroku 2 + podatność 10 lat + gleba + teren  ->  działania długofalowe
    KROK 3b agrotechnika    ryzyko z kroku 2 + bieżące przyczyny (bilans, dni bez opadu, temp.)  ->  działania teraz

Każda rekomendacja ma pole `evidence` z liczbami, z których wynika – żeby było wiadomo „dlaczego”.
Progi stanu są te same co w modelu (model.klasa): <10 silny niedobór, <30 niedobór, 30–70 norma, >70 wilgotno.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

PROG_NIEDOBORU = 30.0
PROG_SILNEGO = 10.0
PROG_WILGOTNO = 70.0

MIESIACE = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
            7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII"}

# Wrażliwość na suszę (0–1) i miesiące krytyczne dla plonu (największe zapotrzebowanie na wodę).
UPRAWY = {
    "zboza-ozime":    {"label": "Zboża ozime",             "sensitivity": 0.55, "okres": [4, 5, 6, 7], "krytyczne": [5, 6],
                       "faza": "strzelanie w źdźbło i kłoszenie"},
    "zboza-jare":     {"label": "Zboża jare",              "sensitivity": 0.60, "okres": [4, 5, 6, 7], "krytyczne": [5, 6],
                       "faza": "strzelanie w źdźbło i kłoszenie"},
    "kukurydza":      {"label": "Kukurydza",               "sensitivity": 0.80, "okres": [5, 6, 7, 8, 9], "krytyczne": [7, 8],
                       "faza": "wiechowanie i kwitnienie"},
    "rzepak":         {"label": "Rzepak i rzepik",         "sensitivity": 0.68, "okres": [3, 4, 5, 6, 7], "krytyczne": [4, 5],
                       "faza": "kwitnienie i zawiązywanie łuszczyn"},
    "burak-cukrowy":  {"label": "Burak cukrowy",           "sensitivity": 0.78, "okres": [4, 5, 6, 7, 8, 9, 10], "krytyczne": [7, 8],
                       "faza": "przyrost korzenia"},
    "ziemniaki":      {"label": "Ziemniaki",               "sensitivity": 0.82, "okres": [5, 6, 7, 8, 9], "krytyczne": [6, 7],
                       "faza": "zawiązywanie i przyrost bulw"},
    "straczkowe":     {"label": "Rośliny strączkowe",      "sensitivity": 0.70, "okres": [4, 5, 6, 7, 8], "krytyczne": [6, 7],
                       "faza": "kwitnienie i zawiązywanie strąków"},
    "uzytki-zielone": {"label": "Użytki zielone",          "sensitivity": 0.60, "okres": [4, 5, 6, 7, 8, 9, 10], "krytyczne": [5, 6, 7, 8],
                       "faza": "odrastanie po pokosach"},
    "drzewa-owocowe": {"label": "Drzewa i krzewy owocowe", "sensitivity": 0.72, "okres": [4, 5, 6, 7, 8, 9], "krytyczne": [5, 6, 7],
                       "faza": "zawiązywanie i wzrost owoców"},
}

SEZON_WEGETACJI = {4, 5, 6, 7, 8, 9, 10}


def _f(v) -> Optional[float]:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v == v else None  # NaN -> None


def _gleba(cechy: dict) -> dict:
    """Cechy glebowe; gdy SoilGrids nie miał danych (pojemność = brak), wszystkie = None."""
    if _f(cechy.get("pojemnosc_wodna_mm")) is None:
        return {"piasek": None, "c_org": None, "pojemnosc": None}
    return {"piasek": _f(cechy.get("piasek_0_30")), "c_org": _f(cechy.get("c_org_0_30")),
            "pojemnosc": _f(cechy.get("pojemnosc_wodna_mm"))}


def _dni(v) -> str:
    v = _f(v)
    if v is None:
        return "brak danych"
    n = int(v)
    return f"{n} dzień" if n == 1 else f"{n} dni"


def _fmt(v, unit="", nd=0) -> str:
    v = _f(v)
    return "brak danych" if v is None else f"{v:.{nd}f}{unit}"


# ------------------------------------------------------------------ KROK 1
def krok1_ocena(percentyl: float, q10: Optional[float], q90: Optional[float],
                szereg: list[dict], prognoza: Optional[dict] = None) -> dict:
    if percentyl < PROG_SILNEGO:
        stan, kolor = "Silny niedobór wody", "red"
    elif percentyl < PROG_NIEDOBORU:
        stan, kolor = "Niedobór wody", "red"
    elif percentyl <= PROG_WILGOTNO:
        stan, kolor = "Wilgotność w normie", "green"
    else:
        stan, kolor = "Gleba wilgotna", "green"

    # pewność względem progu niedoboru – z przedziału Q10–Q90 modelu
    if q10 is None or q90 is None:
        pewnosc = "brak przedziału"
    elif q90 < PROG_NIEDOBORU:
        pewnosc = "niedobór pewny"
    elif percentyl < PROG_NIEDOBORU:
        pewnosc = "niedobór prawdopodobny"
    elif q10 < PROG_NIEDOBORU:
        pewnosc = "niedobór możliwy"
    else:
        pewnosc = "niedobór mało prawdopodobny"

    # trend z ostatnich 7 dni oceny modelu
    oceny = [p.get("ocena") for p in szereg[-8:] if p.get("ocena") is not None]
    trend, zmiana = "brak danych", None
    if len(oceny) >= 2:
        zmiana = oceny[-1] - oceny[0]
        trend = "wysycha" if zmiana <= -8 else "nawilża się" if zmiana >= 8 else "stabilnie"

    opis = f"Gleba jest wilgotniejsza niż w {percentyl:.0f}% dni o tej porze roku z ostatnich 10 lat."
    if q10 is not None and q90 is not None:
        opis += f" Przedział modelu {q10:.0f}–{q90:.0f}: {pewnosc}."
    if zmiana is not None:
        opis += f" W ostatnim tygodniu {trend} ({zmiana:+.0f} pkt)."

    if prognoza:
        opis += (f" Prognoza na {prognoza['data']}: {prognoza['ocena']:.0f} "
                 f"(przedział {prognoza['q10']:.0f}–{prognoza['q90']:.0f}, na podstawie: {prognoza['zrodlo_pogody']}).")

    if kolor == "green" and pewnosc == "niedobór możliwy":
        kolor = "olive"
    return {"stan": stan, "kolor": kolor, "pewnosc": pewnosc, "trend": trend,
            "zmiana_7d": None if zmiana is None else round(zmiana, 1), "opis": opis}


# ------------------------------------------------------------------ KROK 2
def krok2_sugestia(k1: dict, percentyl: float, q10: Optional[float], q90: Optional[float],
                   uprawa_key: Optional[str], dzien: date, prognoza: Optional[dict] = None) -> dict:
    profil = UPRAWY.get(uprawa_key or "")
    miesiac = dzien.month
    w_sezonie = miesiac in (profil["okres"] if profil else SEZON_WEGETACJI)

    if profil:
        sens = profil["sensitivity"]
        krytyczna = miesiac in profil["krytyczne"]
        # próg niedoboru dla uprawy: wrażliwe uprawy reagują wcześniej, w fazie krytycznej jeszcze wcześniej
        prog = PROG_NIEDOBORU + (sens - 0.6) * 25 + (5 if krytyczna else 0)
    else:
        sens, krytyczna, prog = 0.6, False, PROG_NIEDOBORU

    dolna = q10 if q10 is not None else percentyl
    # działaj z wyprzedzeniem: jeśli za 7 dni ma być wyraźnie sucho, liczy się prognoza
    prognoza_gorsza = bool(prognoza) and prognoza["ocena"] < percentyl - 5 and prognoza["ocena"] < prog
    p_ryz = prognoza["ocena"] if prognoza_gorsza else percentyl
    dolna = prognoza["q10"] if prognoza_gorsza else dolna
    pewny = prognoza_gorsza or k1["pewnosc"] in ("niedobór pewny", "niedobór prawdopodobny")
    if p_ryz > PROG_WILGOTNO:
        ryzyko = "nadmiar wody"
    elif p_ryz < prog and pewny:
        ryzyko = "wysokie"
    elif p_ryz < prog or dolna < prog:
        ryzyko = "umiarkowane"
    else:
        ryzyko = "niskie"
    if not w_sezonie and ryzyko in ("wysokie", "umiarkowane"):
        ryzyko = "umiarkowane"  # poza wegetacją niedobór nie uderza bezpośrednio w plon

    nazwa = profil["label"] if profil else "uprawy"
    faza = f" – trwa faza krytyczna ({profil['faza']})" if profil and krytyczna else ""

    if not w_sezonie:
        tytul = (f"{nazwa}: poza okresem wegetacji – czas na odbudowę zapasu wody" if profil
                 else "Poza sezonem wegetacji – czas na odbudowę zapasu wody")
        opis = ("Niedobór teraz nie szkodzi roślinom bezpośrednio, ale zmniejsza zapas wody na wiosnę. "
                "Priorytetem jest zatrzymanie wody z opadów zimowych i roztopów.")
    elif ryzyko == "wysokie":
        tytul = f"Wysokie ryzyko stresu wodnego dla: {nazwa}{faza}"
        opis = ("Model wskazuje niedobór wody w strefie korzeniowej. "
                + ("W tej fazie niedobór najmocniej obniża plon – działaj teraz. " if krytyczna else "")
                + "Ogranicz straty wody z gleby i – jeśli masz możliwość – przygotuj nawadnianie.")
    elif ryzyko == "umiarkowane":
        tytul = f"Umiarkowane ryzyko dla: {nazwa}{faza}"
        opis = ("Stan jest na granicy niedoboru albo przedział niepewności modelu przecina próg. "
                "Sprawdź wilgotność w polu przed decyzjami, które kosztują (nawadnianie, nawożenie).")
    elif ryzyko == "nadmiar wody":
        tytul = f"Gleba wilgotniejsza niż zwykle – {nazwa}"
        opis = ("Niedoboru nie ma. Uważaj na ugniatanie gleby ciężkim sprzętem i choroby grzybowe; "
                "to dobry moment, by zatrzymać nadwyżkę wody na działce.")
    else:
        tytul = f"Brak zagrożenia niedoborem dla: {nazwa}"
        opis = "Wilgotność wystarcza. Utrzymuj praktyki chroniące wodę w glebie i obserwuj prognozę."

    przedz = f" (przedział {q10:.0f}–{q90:.0f})" if q10 is not None and q90 is not None else ""
    if prognoza_gorsza:
        przedz += f", prognoza na {prognoza['data']}: {prognoza['ocena']:.0f}"
    uzasadnienie = (f"percentyl {percentyl:.0f}{przedz} vs próg dla uprawy {prog:.0f}; "
                    f"trend: {k1['trend']}; miesiąc {MIESIACE[miesiac]}"
                    + (f" (krytyczne: {', '.join(MIESIACE[m] for m in profil['krytyczne'])})" if profil else ""))
    return {"ryzyko": ryzyko, "prog": round(prog, 1), "faza_krytyczna": krytyczna, "w_sezonie": w_sezonie,
            "uprawa": profil["label"] if profil else None, "title": tytul, "detail": opis,
            "evidence": uzasadnienie}


# ------------------------------------------------------------------ KROK 3a – retencja
def krok3a_retencja(k2: dict, cechy: dict, podatnosc: dict) -> list[dict]:
    pod = {m: float(v) for m, v in (podatnosc or {}).items()}
    srednia_pod = sum(pod.values()) / len(pod) if pod else None
    max_m, max_pod = (max(pod.items(), key=lambda kv: kv[1]) if pod else (None, None))
    g = _gleba(cechy)
    piasek, pojemnosc, c_org = g["piasek"], g["pojemnosc"], g["c_org"]
    spadek = _f(cechy.get("spadek_proc"))
    wzgl = _f(cechy.get("wzgledna_wys_m"))

    podatna = (srednia_pod is not None and srednia_pod >= 0.3) or (max_pod is not None and max_pod >= 0.5)
    pilnosc = "Pilne" if podatna and k2["ryzyko"] == "wysokie" else "Polecane" if podatna or k2["ryzyko"] in ("wysokie", "umiarkowane") else "Długoterminowe"
    pod_txt = (f"niedobór w {max_m} w {max_pod * 10:.0f}/10 lat, średnio {srednia_pod * 10:.1f}/10 w sezonie"
               if max_pod is not None else "brak danych o podatności")

    rek: list[dict] = []

    # gleba słabo magazynuje wodę
    if (piasek is not None and piasek >= 55) or (pojemnosc is not None and pojemnosc < 130) or (c_org is not None and c_org < 10):
        rek.append({
            "title": "Zwiększ zdolność gleby do magazynowania wody",
            "category": "retention", "priority": pilnosc,
            "detail": "Podnieś zawartość materii organicznej: obornik lub kompost, przyorywanie słomy, "
                      "międzyplony. Każdy 1% próchnicy więcej to kilkanaście mm wody więcej w profilu.",
            "evidence": f"piasek {_fmt(piasek, '%')}, pojemność wodna {_fmt(pojemnosc, ' mm')}, "
                        f"C org. {_fmt(c_org, ' g/kg', 1)}; {pod_txt}",
        })

    # teren nachylony – woda ucieka spływem
    if spadek is not None and spadek >= 2:
        rek.append({
            "title": "Ogranicz spływ powierzchniowy ze stoku",
            "category": "retention", "priority": pilnosc,
            "detail": "Uprawiaj w poprzek stoku, zostaw trwałe pasy zadarnione lub buforowe na dole pola "
                      "i utrzymuj okrywę roślinną poza sezonem, by deszcz wsiąkał zamiast spływać.",
            "evidence": f"spadek terenu {spadek:.1f}%; {pod_txt}",
        })

    # obniżenie – naturalne miejsce gromadzenia wody
    if wzgl is not None and wzgl <= -1:
        rek.append({
            "title": "Wykorzystaj obniżenie terenu do małej retencji",
            "category": "retention", "priority": pilnosc,
            "detail": "Działka leży niżej niż otoczenie – woda spływa tu naturalnie. Rozważ oczko wodne, "
                      "zbiornik lub zastawkę na rowie, by zatrzymać wodę z roztopów na lato.",
            "evidence": f"teren {abs(wzgl):.1f} m poniżej otoczenia (±150 m); {pod_txt}",
        })
    elif podatna and (spadek is None or spadek < 2):
        rek.append({
            "title": "Zatrzymaj wodę z rowów melioracyjnych",
            "category": "retention", "priority": pilnosc,
            "detail": "Na płaskim terenie rowy odprowadzają wodę, której latem brakuje. Zamknij zastawki "
                      "po roztopach (lub zgłoś to spółce wodnej), by podnieść poziom wody gruntowej.",
            "evidence": f"teren płaski (spadek {_fmt(spadek, '%', 1)}); {pod_txt}",
        })

    if k2["ryzyko"] == "nadmiar wody":
        rek.insert(0, {
            "title": "Zatrzymaj nadwyżkę wody na działce",
            "category": "retention", "priority": "Polecane",
            "detail": "Zamiast szybko odprowadzać wodę rowami, przytrzymaj ją zastawkami – zapas przyda się "
                      "w okresie, w którym działka zwykle cierpi na niedobór.",
            "evidence": pod_txt,
        })

    if not rek:
        rek.append({
            "title": "Utrzymuj okrywę gleby przez cały rok",
            "category": "retention", "priority": "Długoterminowe",
            "detail": "Międzyplony i resztki pożniwne ograniczają parowanie i spływ; to podstawa retencji "
                      "glebowej także na działkach o dobrych warunkach.",
            "evidence": f"gleba i teren bez wyraźnych słabych punktów; {pod_txt}",
        })
    return rek[:3]


# ------------------------------------------------------------------ KROK 3b – agrotechnika
def krok3b_agrotechnika(k2: dict, cechy: dict, uprawa_key: Optional[str]) -> list[dict]:
    dni = _f(cechy.get("dni_bez_opadu"))
    bilans30 = _f(cechy.get("bilans_30"))
    bilans60_z = _f(cechy.get("bilans_60_z"))
    tmax = _f(cechy.get("tmax_14"))
    g = _gleba(cechy)
    pojemnosc, piasek = g["pojemnosc"], g["piasek"]
    ryzyko = k2["ryzyko"]
    rek: list[dict] = []

    if not k2["w_sezonie"]:
        return [{
            "title": "Zostaw okrywę na zimę, nie zostawiaj gołej roli",
            "category": "agrotechnical", "priority": "Polecane",
            "detail": "Międzyplony ozime lub mulcz ze słomy zwiększają wsiąkanie wody z roztopów. "
                      "Unikaj jesiennych zabiegów na mokrej glebie, które ją zagęszczają.",
            "evidence": f"poza sezonem wegetacji; ryzyko z kroku 2: {ryzyko}",
        }]

    if ryzyko in ("wysokie", "umiarkowane"):
        rek.append({
            "title": "Ogranicz parowanie z gleby",
            "category": "agrotechnical", "priority": "Pilne" if ryzyko == "wysokie" else "Polecane",
            "detail": "Zostaw resztki pożniwne na powierzchni (mulcz), zrezygnuj z orki i głębokich uprawek – "
                      "każde odwrócenie gleby to utrata wody. Uprawki wykonuj płytko i rano.",
            "evidence": f"bilans wodny 30 dni {_fmt(bilans30, ' mm')}, "
                        f"bez opadu ≥5 mm: {_dni(dni)}, śr. temp. maks. {_fmt(tmax, '°C', 1)}",
        })
        rek.append({
            "title": "Usuń chwasty konkurujące o wodę i dostosuj nawożenie",
            "category": "agrotechnical", "priority": "Polecane",
            "detail": "Chwasty zużywają tę samą wodę co uprawa. Przy suchej glebie azot posypowy słabo działa – "
                      "odłóż pogłówne nawożenie do opadów lub zastosuj nawożenie dolistne.",
            "evidence": f"bilans 60 dni {_fmt(bilans60_z, ' σ', 1)} względem normy; ryzyko: {ryzyko}",
        })

    if ryzyko == "wysokie":
        if pojemnosc is not None:
            dawka = max(15, min(35, 0.25 * pojemnosc))
            dawka_txt = f"ok. {dawka:.0f} mm na zabieg"
        else:
            dawka_txt = "20–25 mm na zabieg"
        lekka = piasek is not None and piasek >= 55
        rek.insert(1 if rek else 0, {
            "title": "Nawadniaj" + (" w fazie krytycznej" if k2["faza_krytyczna"] else " jeśli masz taką możliwość"),
            "category": "irrigation", "priority": "Pilne" if k2["faza_krytyczna"] else "Polecane",
            "detail": f"Dawka {dawka_txt}" + (", na glebie lekkiej mniejszymi dawkami, częściej" if lekka else "")
                      + ". Podlewaj wieczorem lub rano, by ograniczyć straty na parowanie.",
            "evidence": (f"pojemność wodna gleby {_fmt(pojemnosc, ' mm')}, piasek {_fmt(piasek, '%')}; "
                         if pojemnosc is not None else "brak danych glebowych – dawka orientacyjna; ")
                        + k2["evidence"],
        })
    elif ryzyko == "umiarkowane":
        rek.insert(0, {
            "title": "Sprawdź wilgotność w polu przed decyzją",
            "category": "management", "priority": "Polecane",
            "detail": "Wykop dołek na 20–30 cm: jeśli gleba nie formuje się w kulkę w dłoni, wilgoci jest za mało. "
                      "Dopiero wtedy decyduj o nawadnianiu.",
            "evidence": k2["evidence"],
        })
    elif ryzyko == "nadmiar wody":
        rek.append({
            "title": "Nie wjeżdżaj ciężkim sprzętem na mokre pole",
            "category": "agrotechnical", "priority": "Polecane",
            "detail": "Mokra gleba łatwo się ugniata, a zagęszczona warstwa gorzej przyjmuje wodę w czasie suszy. "
                      "Odłóż zabiegi do przeschnięcia wierzchniej warstwy; obserwuj choroby grzybowe.",
            "evidence": f"{k2['evidence']}; bilans 30 dni {_fmt(bilans30, ' mm')}",
        })
    else:
        rek.append({
            "title": "Utrzymuj mulcz i ogranicz zbędne uprawki",
            "category": "agrotechnical", "priority": "Długoterminowe",
            "detail": "Wilgoci wystarcza. Zachowaj resztki na powierzchni i nie przesuszaj gleby niepotrzebnymi "
                      "zabiegami – to bufor na kolejne suche tygodnie.",
            "evidence": f"{k2['evidence']}; bez opadu ≥5 mm: {_dni(dni)}",
        })
    return rek[:3]


# ------------------------------------------------------------------ przyczyny
def przyczyny(cechy: dict) -> list[dict]:
    """Czynniki posortowane wg tego, jak bardzo odbiegają od normy."""
    wynik = []
    z60, b60 = _f(cechy.get("bilans_60_z")), _f(cechy.get("bilans_60"))
    if z60 is not None:
        wynik.append((abs(z60), {
            "title": "Bilans wodny (60 dni)",
            "value": f"{_fmt(b60, ' mm')}, {z60:+.1f} σ od normy",
            "detail": "Opady minus parowanie (ET0). Wartość ujemna i poniżej normy oznacza, że gleba więcej traci, niż dostaje.",
        }))
    z30, b30 = _f(cechy.get("bilans_30_z")), _f(cechy.get("bilans_30"))
    if z30 is not None:
        wynik.append((abs(z30) * 0.9, {
            "title": "Bilans wodny (30 dni)",
            "value": f"{_fmt(b30, ' mm')}, {z30:+.1f} σ od normy",
            "detail": "Krótszy horyzont – pokazuje, czy sytuacja ostatnio się pogarsza czy poprawia.",
        }))
    dni = _f(cechy.get("dni_bez_opadu"))
    if dni is not None:
        wynik.append((dni / 10, {
            "title": "Dni bez opadu ≥5 mm",
            "value": _dni(dni),
            "detail": "Im dłużej bez wydatnego deszczu, tym szybciej przesycha warstwa korzeniowa.",
        }))
    opad = _f(cechy.get("opad_30"))
    if opad is not None:
        wynik.append((0.5, {
            "title": "Opady (30 dni)",
            "value": f"{opad:.0f} mm",
            "detail": "Suma opadów z ostatniego miesiąca.",
        }))
    tmax = _f(cechy.get("tmax_14"))
    if tmax is not None:
        wynik.append((max(0.0, (tmax - 26) / 3), {
            "title": "Temperatura (14 dni)",
            "value": f"śr. maks. {tmax:.1f}°C",
            "detail": "Wysoka temperatura zwiększa parowanie i zapotrzebowanie roślin na wodę.",
        }))
    poj = _gleba(cechy)["pojemnosc"]
    if poj is not None:
        wynik.append((1.2 if poj < 130 else 0.3, {
            "title": "Pojemność wodna gleby",
            "value": f"{poj:.0f} mm w 0–100 cm" + (f", piasek {cechy['piasek_0_30']:.0f}%" if _f(cechy.get("piasek_0_30")) is not None else ""),
            "detail": "Ile wody dostępnej dla roślin gleba może zmagazynować. Mało = szybciej wysycha.",
        }))
    wynik.sort(key=lambda x: x[0], reverse=True)
    return [w for _, w in wynik[:4]]


# ------------------------------------------------------------------ całość
def zbuduj(wynik: dict, szereg: list[dict], uprawa_key: Optional[str], dzien: date) -> dict:
    # `is None`, nie `or`: percentyl 0 (najsilniejsza susza) to poprawna wartość
    percentyl = float(50 if wynik.get("percentyl") is None else wynik["percentyl"])
    przedzial = wynik.get("przedzial_10_90") or [None, None]
    q10, q90 = _f(przedzial[0]), _f(przedzial[1])
    cechy = wynik.get("cechy") or {}
    podatnosc = wynik.get("podatnosc_odsetek_lat_z_niedoborem") or {}

    prognoza = wynik.get("prognoza_7d")
    k1 = krok1_ocena(percentyl, q10, q90, szereg, prognoza)
    k2 = krok2_sugestia(k1, percentyl, q10, q90, uprawa_key, dzien, prognoza)
    retencja = krok3a_retencja(k2, cechy, podatnosc)
    agro = krok3b_agrotechnika(k2, cechy, uprawa_key)

    wartosci = list(podatnosc.values())
    return {
        "krok1": k1,
        "prognoza_7d": prognoza,
        "krok2": k2,
        "retencja": retencja,
        "agrotechnika": agro,
        "przyczyny": przyczyny(cechy),
        "srednia_podatnosc": round(sum(wartosci) / len(wartosci), 2) if wartosci else None,
        "miesiace_ryzyka": [m for m, v in sorted(podatnosc.items(), key=lambda kv: kv[1], reverse=True)[:3] if v > 0],
        "zakres": f"{q10:.0f}–{q90:.0f}" if q10 is not None and q90 is not None else "brak przedziału",
    }
