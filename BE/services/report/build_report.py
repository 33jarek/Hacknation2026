from __future__ import annotations

from datetime import datetime
from typing import Dict, List


SOURCE_CATALOG = [
    {
        "name": "ULDK GUGiK",
        "category": "parcel and geometry",
        "label": "Działka i geometria",
        "url": "https://uldk.gugik.gov.pl/opis.html",
        "note": "Wyszukiwanie działki i geometria ewidencyjna w układzie EPSG:4326.",
    },
    {
        "name": "Open-Meteo",
        "category": "meteorological",
        "label": "Dane meteorologiczne",
        "url": "https://open-meteo.com/en/docs",
        "note": "Historyczne opady, temperatura, ET0 oraz opcjonalna krótka prognoza.",
    },
    {
        "name": "ISRIC SoilGrids",
        "category": "soil",
        "label": "Gleba",
        "url": "https://docs.isric.org/globaldata/soilgrids/",
        "note": "Przybliżenie tekstury i właściwości wierzchniej warstwy gleby. Dostępność publicznego API może się zmieniać.",
    },
    {
        "name": "Microsoft Planetary Computer",
        "category": "satellite",
        "label": "Dane satelitarne",
        "url": "https://planetarycomputer.microsoft.com/docs/",
        "note": "Zobrazowania Landsat Collection 2 użyte do policzenia NDVI w geometrii działki.",
    },
    {
        "name": "OpenTopoData",
        "category": "terrain",
        "label": "Ukształtowanie terenu",
        "url": "https://www.opentopodata.org/api/",
        "note": "Próbki wysokości SRTM do oszacowania lokalnej deniwelacji.",
    },
    {
        "name": "OpenStreetMap Overpass API",
        "category": "hydrological context",
        "label": "Kontekst hydrologiczny",
        "url": "https://overpass-api.de/",
        "note": "Pobliskie cieki, rowy i zbiorniki oznaczone w OpenStreetMap.",
    },
]


def build_report(summary: Dict, recommendations: List[Dict], missing_data: List[str], limitations: List[str]) -> Dict:
    generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    sources = []
    missing_prefixes = {item.split(":", 1)[0] for item in missing_data}
    for source in SOURCE_CATALOG:
        category_key = {
            "parcel and geometry": "parcel",
            "meteorological": "weather",
            "soil": "soil",
            "satellite": "satellite",
            "terrain": "terrain",
            "hydrological context": "hydro",
        }[source["category"]]
        sources.append(
            {
                **source,
                "accessed_at": generated_at,
                "status": "missing" if category_key in missing_prefixes else "used",
            }
        )

    return {
        "parcel": summary["parcel"],
        "crop": summary["crop_label"],
        "crop_key": summary["crop_key"],
        "analysis_date": summary["analysis_date"],
        "current_status": summary["current_status"],
        "historical_context": summary["historical_context"],
        "retention_context": summary["retention_context"],
        "irrigation_guidance": summary["irrigation_guidance"],
        "signal_snapshot": summary["signal_snapshot"],
        "recommendations": recommendations,
        "sources": sources,
        "limitations": limitations,
        "missing_data": missing_data,
        "generated_at": generated_at,
    }
