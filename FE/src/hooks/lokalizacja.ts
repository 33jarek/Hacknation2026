import type { Geometry } from "geojson";

export type Dzialka = {
  id: string;
  numer: string | null;
  obreb: string | null;
  gmina: string | null;
  powiat: string | null;
  wojewodztwo: string | null;
  powierzchnia_ha: number | null;
  geometry: Geometry | null;
  centroid: { lat: number; lon: number } | null;
};

export type WybranaLokalizacja = {
  lat: number;
  lon: number;
  label: string;
  parcel: Dzialka | null;
  parcel_error: string | null;
  /** skąd przyszła lokalizacja – mapa przybliża się tylko przy wyszukiwaniu */
  zrodlo?: "mapa" | "wyszukiwanie" | "start";
};

export type TrybWyszukiwania = "adres" | "dzialka" | "wspolrzedne";

export function apiBase(): string {
  const raw = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");
  if (!raw) return "/api";
  return raw.endsWith("/api") ? raw : `${raw}/api`;
}

async function pobierz(path: string, params: Record<string, string>): Promise<WybranaLokalizacja> {
  const qs = new URLSearchParams(params).toString();
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}?${qs}`);
  } catch {
    throw new Error("Brak połączenia z serwerem");
  }
  if (!response.ok) {
    let message = `Błąd ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  return response.json();
}

export function lokalizacjaZPunktu(lat: number, lon: number) {
  return pobierz("/lokalizacja/punkt", { lat: String(lat), lon: String(lon) });
}

export function lokalizacjaZAdresu(q: string) {
  return pobierz("/lokalizacja/adres", { q });
}

export function lokalizacjaZDzialki(id: string) {
  return pobierz("/lokalizacja/dzialka", { id });
}

/** "52.23, 21.01" / "52,23 21,01" / "52.23;21.01" → [lat, lon] */
export function parsujWspolrzedne(text: string): [number, number] | null {
  let t = text.trim();
  // "52,23 21,01" – przecinek dziesiętny, separatorem jest spacja
  if (!t.includes(".") && /\s/.test(t)) t = t.replace(/,/g, ".");
  const liczby = t
    .split(/[\s;,]+/)
    .filter(Boolean)
    .map(Number);
  if (liczby.length !== 2 || liczby.some((n) => !Number.isFinite(n))) return null;
  let [a, b] = liczby;
  // ktoś podał lon, lat
  if (a >= 14 && a <= 25 && b >= 49 && b <= 55) [a, b] = [b, a];
  return [a, b];
}

export function wPolsce(lat: number, lon: number) {
  return lat >= 49 && lat <= 55 && lon >= 14 && lon <= 25;
}

/** Pobiera raport PDF z analizy i zapisuje go w przeglądarce. */
export async function pobierzRaportPdf(params: {
  lokalizacja: WybranaLokalizacja;
  dataAnalizy: string;
  uprawa: string;
}): Promise<void> {
  const { lokalizacja, dataAnalizy, uprawa } = params;
  // geometria działki nie jest potrzebna w raporcie
  const dzialka = lokalizacja.parcel ? { ...lokalizacja.parcel, geometry: undefined } : null;
  let response: Response;
  try {
    response = await fetch(`${apiBase()}/raport`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat: lokalizacja.lat,
        lon: lokalizacja.lon,
        data_analizy: dataAnalizy,
        uprawa: uprawa || null,
        lokalizacja_label: lokalizacja.label,
        dzialka,
      }),
    });
  } catch {
    throw new Error("Brak połączenia z serwerem");
  }
  if (!response.ok) {
    let message = `Błąd ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `raport_wilgotnosc_${dataAnalizy}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
