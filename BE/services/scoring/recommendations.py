from __future__ import annotations

from typing import Dict, List


DISPLAY_LABELS = {
    "low": "niski",
    "medium": "średni",
    "moderate": "umiarkowany",
    "high": "wysoki",
    "good": "dobry",
    "flat": "płaski",
    "gently undulating": "lekko falisty",
    "rolling": "pagórkowaty",
    "strong": "silne",
    "limited": "słabe",
}


def _label(value):
    if value is None or value == "":
        return "brak danych"
    return DISPLAY_LABELS.get(value, value)


def build_recommendations(summary: Dict) -> List[Dict]:
    recommendations: List[Dict] = []
    weather = summary["signal_snapshot"].get("weather", {})
    soil = summary["signal_snapshot"].get("soil", {})
    terrain = summary["signal_snapshot"].get("terrain", {})
    hydro = summary["signal_snapshot"].get("hydro", {})

    if soil.get("water_holding_class") in {"low", "medium"}:
        recommendations.append(
            {
                "title": "Zwiększ zatrzymywanie wilgoci na polu",
                "category": "retention",
                "priority": "high",
                "rationale": "Profil gleby wskazuje ograniczoną zdolność zatrzymywania wody, co zwiększa ryzyko stresu suszowego między opadami.",
                "evidence": [
                    f"Zawartość piasku: {soil.get('sand_pct', 'brak danych')}%",
                    "Klasa retencji glebowej: "
                    + {"low": "niska", "medium": "średnia", "good": "dobra"}.get(
                        soil.get("water_holding_class"),
                        _label(soil.get("water_holding_class")),
                    ),
                    f"Ostatni bilans klimatyczny: {weather.get('recent_balance_mm', 'brak danych')} mm",
                ],
                "confidence": summary["current_status"]["confidence"],
            }
        )

    if terrain.get("runoff_risk_score", 0) >= 35:
        recommendations.append(
            {
                "title": "Spowolnij spływ powierzchniowy na działce",
                "category": "retention",
                "priority": "medium",
                "rationale": "Ukształtowanie terenu wskazuje, że część opadu może szybko odpływać z działki zamiast wsiąkać w profil glebowy.",
                "evidence": [
                    f"Ukształtowanie: {_label(terrain.get('terrain_class'))}",
                    f"Deniwelacja: {terrain.get('local_relief_m', 'brak danych')} m",
                ],
                "confidence": summary["current_status"]["confidence"],
            }
        )

    if hydro.get("nearby_water_features", 0) >= 2:
        feature_names = hydro.get("feature_names") or []
        recommendations.append(
            {
                "title": "Sprawdź możliwości retencji przy rowach i ciekach",
                "category": "retention",
                "priority": "medium",
                "rationale": "W otoczeniu działki są oznaczone obiekty wodne. Mogą one sprzyjać spowolnieniu odpływu albo lokalnemu zatrzymaniu wody, o ile jest to możliwe technicznie i prawnie.",
                "evidence": [
                    f"Obiekty wodne w okolicy: {hydro.get('nearby_water_features', 'brak danych')}",
                    "Nazwy obiektów: " + (", ".join(feature_names) if feature_names else "występują w otoczeniu"),
                ],
                "confidence": summary["current_status"]["confidence"],
            }
        )

    if summary["historical_context"]["susceptibility_level"] in {"moderate", "high"}:
        recommendations.append(
            {
                "title": "Wzmocnij zabiegi chroniące wilgoć w glebie",
                "category": "agrotechnical",
                "priority": "high",
                "rationale": "Dane wieloletnie wskazują powtarzające się niedobory wilgoci w sezonie wegetacyjnym, dlatego warto chronić wodę już zgromadzoną w glebie.",
                "evidence": [
                    "Miesiące ryzyka: " + ", ".join(summary["historical_context"].get("high_risk_months", [])),
                    f"Częstość dni suchych w 10 latach: {summary['historical_context'].get('drought_frequency_pct', 'brak danych')}%",
                ],
                "confidence": summary["current_status"]["confidence"],
            }
        )

    if summary["irrigation_guidance"]["need_level"] == "high":
        recommendations.append(
            {
                "title": "Przygotuj nawadnianie tylko na okres największej potrzeby",
                "category": "irrigation",
                "priority": "high",
                "rationale": "Ostatni niedobór, wrażliwość uprawy i krótka prognoza wskazują podwyższone zapotrzebowanie na nawadnianie w najbliższym czasie.",
                "evidence": [
                    f"Wskaźnik potrzeby nawadniania: {summary['irrigation_guidance'].get('need_score', 'brak danych')}",
                    f"Prognoza opadu na 7 dni: {summary['irrigation_guidance'].get('forecast_precipitation_7d_mm', 'brak danych')} mm",
                    f"Prognoza ET0 na 7 dni: {summary['irrigation_guidance'].get('forecast_et0_7d_mm', 'brak danych')} mm",
                ],
                "confidence": summary["current_status"]["confidence"],
            }
        )

    if not recommendations:
        recommendations.append(
            {
                "title": "Utrzymaj obserwację pola",
                "category": "management",
                "priority": "low",
                "rationale": "Obecne sygnały nie wskazują silnej i jednoznacznej potrzeby działań poza bieżącą obserwacją uprawy.",
                "evidence": [
                    f"Bieżący poziom ryzyka: {_label(summary['current_status'].get('risk_level'))}",
                    f"Podatność historyczna: {_label(summary['historical_context'].get('susceptibility_level'))}",
                ],
                "confidence": summary["current_status"]["confidence"],
            }
        )

    return recommendations
