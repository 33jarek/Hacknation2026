"""Raport PDF z analizy wilgotności gleby (ten sam wynik, który widzi użytkownik w aplikacji)."""
from __future__ import annotations

import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ZIELONY = colors.HexColor("#1f5b46")
SZARY = colors.HexColor("#6f8172")
TEKST = colors.HexColor("#26352b")
RAMKA = colors.HexColor("#e2e8dc")
CZERWONY = colors.HexColor("#b91c1c")
OLIWKOWY = colors.HexColor("#7f8f2a")   # = text-[#7f8f2a] w StatusCard.tsx

_FONT_DIR = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold")

S = {
    "tytul": ParagraphStyle("tytul", fontName="DejaVu-Bold", fontSize=16, leading=20, textColor=TEKST),
    "pod": ParagraphStyle("pod", fontName="DejaVu", fontSize=8.5, leading=11, textColor=SZARY),
    "h2": ParagraphStyle("h2", fontName="DejaVu-Bold", fontSize=11, leading=14, textColor=TEKST,
                         spaceBefore=10, spaceAfter=4),
    "txt": ParagraphStyle("txt", fontName="DejaVu", fontSize=9, leading=12.5, textColor=TEKST, alignment=TA_LEFT),
    "mały": ParagraphStyle("maly", fontName="DejaVu", fontSize=7.5, leading=10, textColor=SZARY),
    "stan": ParagraphStyle("stan", fontName="DejaVu-Bold", fontSize=13, leading=16, textColor=TEKST),
    "nagl": ParagraphStyle("nagl", fontName="DejaVu-Bold", fontSize=7.5, leading=9.5, textColor=SZARY),
    "bold": ParagraphStyle("bold", fontName="DejaVu-Bold", fontSize=9, leading=12.5, textColor=TEKST),
}

PLIK_META = Path(__file__).resolve().parent / "model_wilgotnosc_meta.json"


def _esc(t) -> str:
    return (str(t) if t is not None else "–").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt(v, unit="", nd=1) -> str:
    return "–" if v is None else f"{v:.{nd}f}{unit}"


def _data_pl(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(iso)


def _wykres(szereg: list[dict], prognoza: Optional[dict]) -> Optional[io.BytesIO]:
    tydzien = szereg[-7:]
    if not tydzien:
        return None
    x = list(range(len(tydzien)))
    etykiety = [datetime.strptime(p["data"], "%Y-%m-%d").strftime("%d.%m") for p in tydzien]
    oc = [p.get("ocena") for p in tydzien]
    era = [p.get("era5") for p in tydzien]
    lo = [p.get("q10") for p in tydzien]
    hi = [p.get("q90") for p in tydzien]

    fig, ax = plt.subplots(figsize=(7.2, 2.6), dpi=200)
    ax.fill_between(x, lo, hi, color="#b7cfa3", alpha=0.35, linewidth=0, label="przedział Q10–Q90")
    ax.plot(x, oc, color="#1f5b46", linewidth=2, label="ocena modelu")
    ax.plot(x, era, color="#acc649", linewidth=1.6, marker="o", markersize=3, label="ERA5")
    if prognoza:
        xp = len(tydzien) + 0  # punkt za 7 dni
        ax.plot([x[-1], xp], [oc[-1], prognoza["ocena"]], color="#1f5b46", linewidth=1.4, linestyle="--")
        ax.errorbar([xp], [prognoza["ocena"]],
                    yerr=[[prognoza["ocena"] - prognoza["q10"]], [prognoza["q90"] - prognoza["ocena"]]],
                    fmt="o", color="#1f5b46", markersize=4, capsize=3, label="prognoza +7 dni")
        etykiety = etykiety + [datetime.strptime(prognoza["data"], "%Y-%m-%d").strftime("%d.%m")]
        x = x + [xp]
    ax.axhspan(0, 30, color="#fde2e2", alpha=0.45, linewidth=0)
    ax.set_xticks(x, etykiety, fontsize=7)
    ax.set_ylim(0, 100)
    ax.set_ylabel("percentyl wilgotności", fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(axis="y", color="#e2e8dc", linewidth=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(fontsize=6.5, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.16))
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def _tabela(dane: list[list], szer: list[float], naglowek=True) -> Table:
    # napisy -> akapity, żeby długi tekst się zawijał zamiast nachodzić na sąsiednią kolumnę
    dane = [[Paragraph(_esc(c), S["nagl"] if naglowek and i == 0 else S["txt"]) if isinstance(c, str) else c
             for c in wiersz] for i, wiersz in enumerate(dane)]
    t = Table(dane, colWidths=szer, hAlign="LEFT")
    styl = [
        ("FONT", (0, 0), (-1, -1), "DejaVu", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), TEKST),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RAMKA),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if naglowek:
        styl += [("FONT", (0, 0), (-1, 0), "DejaVu-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), SZARY)]
    t.setStyle(TableStyle(styl))
    return t


def _rekomendacje(lista: list[dict]) -> list:
    out = []
    for r in lista or []:
        kolor = CZERWONY if r.get("priority") == "Pilne" else ZIELONY if r.get("priority") == "Polecane" else SZARY
        blok = [
            Paragraph(f"<b>{_esc(r.get('title'))}</b> &nbsp;<font color='{kolor.hexval()}' size='7.5'>"
                      f"{_esc(r.get('priority'))}</font>", S["bold"]),
            Paragraph(_esc(r.get("detail")), S["txt"]),
        ]
        if r.get("evidence"):
            blok.append(Paragraph(f"Na podstawie: {_esc(r['evidence'])}", S["mały"]))
        blok.append(Spacer(1, 5))
        out.append(KeepTogether(blok))
    return out or [Paragraph("Brak.", S["txt"])]


def zbuduj_pdf(odp: dict, lokalizacja: dict, dzialka: Optional[dict], uprawa_label: Optional[str]) -> bytes:
    ai = odp["ocena_ai"]
    wynik = odp.get("wynik") or {}
    szereg = (odp.get("wykresy") or {}).get("szereg_czasowy") or []
    prognoza = ai.get("prognoza_7d")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Raport stanu wilgotności gleby", author="Drought Predict")
    W = doc.width - 12  # Frame ma 6 pt wewnętrznego marginesu z każdej strony
    e: list = []

    # --- nagłówek
    e.append(Paragraph("Raport stanu wilgotności gleby", S["tytul"]))
    e.append(Paragraph(f"Drought Predict · wygenerowano {datetime.now().strftime('%d.%m.%Y %H:%M')}", S["pod"]))
    e.append(Spacer(1, 8))

    # --- lokalizacja
    wiersze = [
        ["Lokalizacja", Paragraph(_esc(lokalizacja.get("label")), S["txt"])],
        ["Współrzędne", f"{lokalizacja['lat']:.5f}, {lokalizacja['lon']:.5f}"],
    ]
    if dzialka:
        wiersze += [
            ["Działka", Paragraph(_esc(f"nr {dzialka.get('numer') or '–'}, id {dzialka.get('id')}"), S["txt"])],
            ["Obręb / gmina", Paragraph(_esc(", ".join(x for x in (dzialka.get("obreb"), dzialka.get("gmina"),
                                                                     dzialka.get("powiat")) if x)), S["txt"])],
        ]
        if dzialka.get("powierzchnia_ha") is not None:
            wiersze.append(["Powierzchnia", f"{dzialka['powierzchnia_ha']} ha"])
    wiersze += [
        ["Data analizy", _data_pl(wynik.get("data_analizy"))
         + (f" (dane do {_data_pl(wynik.get('dzien_ocenionych_danych'))})"
            if wynik.get("dzien_ocenionych_danych") != wynik.get("data_analizy") else "")],
        ["Uprawa", uprawa_label or "nie wybrano"],
    ]
    e.append(_tabela(wiersze, [35 * mm, W - 35 * mm], naglowek=False))

    # --- krok 1
    e.append(Paragraph("1. Ocena stanu wilgotności (model AI)", S["h2"]))
    # ten sam kolor co w aplikacji (wyznaczony w backendzie z oceny i ryzyka dla uprawy)
    kolor_stanu = {"red": CZERWONY, "olive": OLIWKOWY, "green": ZIELONY}.get(ai.get("kolor"), ZIELONY)
    e.append(Paragraph(f"<font color='{kolor_stanu.hexval()}'>{_esc(ai['status'])}</font>", S["stan"]))
    e.append(Spacer(1, 2))
    e.append(Paragraph(_esc(ai["summary"]), S["txt"]))
    e.append(Spacer(1, 4))
    liczby = [["Percentyl (0 sucho – 100 mokro)", "Przedział Q10–Q90", "Zmiana w 7 dni", "Prognoza +7 dni"],
              [f"{ai['percentyl']:.0f}", ai.get("zakres") or "–",
               "–" if ai.get("zmiana_7d") is None else f"{ai['zmiana_7d']:+.0f}",
               f"{prognoza['ocena']:.0f} ({prognoza['q10']:.0f}–{prognoza['q90']:.0f})" if prognoza else "niedostępna"]]
    e.append(_tabela(liczby, [W / 4] * 4))
    img = _wykres(szereg, prognoza)
    if img:
        e.append(Spacer(1, 6))
        e.append(Image(img, width=W, height=W * 2.6 / 7.2))
        e.append(Paragraph("Percentyl wilgotności gleby 0–100 cm na tle tej samej pory roku z ostatnich 10 lat "
                           "(50 = typowo, poniżej 30 = niedobór – pole zaznaczone na czerwono).", S["mały"]))

    # --- krok 2
    sug = ai.get("sugestia")
    if sug:
        e.append(Paragraph("2. Sugestia dla uprawy", S["h2"]))
        e.append(Paragraph(f"<b>{_esc(sug['title'])}</b>", S["txt"]))
        e.append(Paragraph(_esc(sug["detail"]), S["txt"]))
        e.append(Paragraph(f"Na podstawie: {_esc(sug['evidence'])}", S["mały"]))

    # --- warunki i podatność
    e.append(Paragraph("Warunki przed dniem analizy i podatność działki", S["h2"]))
    pog = ai.get("pogoda") or {}
    pod = ai.get("srednia_podatnosc")
    e.append(_tabela([
        ["Śr. temp. maks. (14 dni)", "Opady (30 dni)", "Woda w glebie 0–100 cm", "Lata z niedoborem (IV–IX)",
         "Miesiące ryzyka"],
        [_fmt(pog.get("temperatura_srednia_c"), "°C"), _fmt(pog.get("opady_30_dni_mm"), " mm"),
         _fmt(pog.get("wilgotnosc_gleby_pct"), "%"), "–" if pod is None else f"{round(pod * 10)}/10",
         ", ".join(ai.get("miesiace_ryzyka") or []) or "–"],
    ], [W * 0.2] * 5))

    # --- przyczyny
    przyczyny = ai.get("causes") or []
    if przyczyny:
        e.append(Paragraph("Co wpływa na wilgotność", S["h2"]))
        e.append(_tabela([["Czynnik", "Wartość", "Znaczenie"]] + [
            [Paragraph(_esc(c["title"]), S["txt"]), Paragraph(_esc(c["value"]), S["txt"]),
             Paragraph(_esc(c["detail"]), S["mały"])] for c in przyczyny
        ], [W * 0.25, W * 0.25, W * 0.5]))

    # --- krok 3
    e.append(Paragraph("3a. Rekomendacje retencyjne", S["h2"]))
    e += _rekomendacje(ai.get("rekomendacje_retencyjne"))
    e.append(Paragraph("3b. Rekomendacje agrotechniczne", S["h2"]))
    e += _rekomendacje(ai.get("rekomendacje_agrotechniczne"))

    # --- metodyka
    e.append(Paragraph("Metodyka, źródła i ograniczenia", S["h2"]))
    metodyka = ("Ocena pochodzi z modelu uczenia maszynowego (gradient boosting) trenowanego na danych z punktów "
                "w całej Polsce. Model łączy ostatni znany stan wilgotności (ERA5-Land) z pogodą z ostatniego "
                "tygodnia, bilansem wodnym, glebą i ukształtowaniem terenu. Rekomendacje wynikają z oceny "
                "(krok 1) i sugestii dla uprawy (krok 2) według jawnych reguł – przy każdej podano liczby, na "
                "podstawie których powstała.")
    try:
        meta = json.loads(PLIK_META.read_text(encoding="utf-8"))
        gb = meta["wyniki_testu"]["gradient_boosting"]
        tr = meta["trening"]
        metodyka += (f" Jakość na latach testowych ({tr['rok_podzialu'] + 1}–2025, niewidzianych w treningu): "
                     f"średni błąd {gb['MAE']:.1f} pkt percentyla, R² {gb['R2']:.2f}, trafność rozpoznania "
                     f"niedoboru {gb.get('trafnosc_niedoboru', 0) * 100:.0f}%.")
    except Exception:
        pass
    e.append(Paragraph(_esc(metodyka), S["txt"]))
    for b in wynik.get("braki_i_ograniczenia") or []:
        e.append(Paragraph(f"• {_esc(b)}", S["mały"]))
    if wynik.get("zrodla"):
        e.append(Spacer(1, 3))
        e.append(Paragraph("Źródła danych: " + _esc("; ".join(wynik["zrodla"])), S["mały"]))
    e.append(Spacer(1, 4))
    e.append(Paragraph("Raport ma charakter doradczy i nie zastępuje oceny stanu pola na miejscu.", S["mały"]))

    def stopka(canvas, doc_):
        canvas.saveState()
        canvas.setFont("DejaVu", 7)
        canvas.setFillColor(SZARY)
        canvas.drawString(doc_.leftMargin, 9 * mm, "Drought Predict – raport stanu wilgotności gleby")
        canvas.drawRightString(A4[0] - doc_.rightMargin, 9 * mm, f"str. {doc_.page}")
        canvas.restoreState()

    doc.build(e, onFirstPage=stopka, onLaterPages=stopka)
    return buf.getvalue()
