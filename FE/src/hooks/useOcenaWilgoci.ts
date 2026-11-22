import { useQuery } from "@tanstack/react-query";

export type PunktWilgotnosci = {
  data: string;
  ocena: number | null;
  q10: number | null;
  q90: number | null;
  era5: number | null;
};

export type PunktGodzinowy = {
  godzina: string;
  ocena: number | null;
  q10: number | null;
  q90: number | null;
  era5: number | null;
};

export type PunktRegresji = {
  rzeczywiste: number;
  przewidziane: number;
};

export type PunktLiniiRegresji = {
  x: number;
  y: number;
};

export type PrzyczynaAI = {
  title: string;
  value: string;
  detail: string;
};

export type RekomendacjaAI = {
  title: string;
  category: "retention" | "agrotechnical" | "irrigation" | "management";
  priority: string;
  detail: string;
  evidence: string;
};

export type OcenaAI = {
  status: string;
  summary: string;
  percentyl: number;
  poziom: string;
  kolor: "red" | "olive" | "green";
  zakres: string;
  srednia_podatnosc: number | null;
  miesiace_ryzyka: string[];
  causes: PrzyczynaAI[];
  recommendations: RekomendacjaAI[];
  uprawa: string | null;
  pogoda: {
    temperatura_srednia_c: number | null;
    opady_30_dni_mm: number | null;
    wilgotnosc_gleby_pct: number | null;
  } | null;
  pogoda_status: "available" | "unavailable";
};

export type OcenaWilgotnosciResponse = {
  status: "success" | "fallback";
  lokalizacja: {
    lat: number;
    lon: number;
  };
  wynik: Record<string, unknown>;
  wykresy: {
    szereg_czasowy: PunktWilgotnosci[];
    szereg_godzinowy?: PunktGodzinowy[];
    dzien_wykresu?: string | null;
    regresja: {
      dostepna: boolean;
      r2: number | null;
      slope: number | null;
      intercept: number | null;
      punkty: PunktRegresji[];
      linia: PunktLiniiRegresji[];
    };
  };
  ocena_ai: OcenaAI;
  rekomendacje: RekomendacjaAI[];
};

type ParametryOceny = {
  lat: number;
  lon: number;
  dataAnalizy: string;
  uprawa?: string;
  enabled?: boolean;
};

async function pobierzOcene({
  lat,
  lon,
  dataAnalizy,
  uprawa,
}: ParametryOceny): Promise<OcenaWilgotnosciResponse> {
  const rawApiUrl = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");
  const endpoint = rawApiUrl
    ? rawApiUrl.endsWith("/api")
      ? `${rawApiUrl}/ocena`
      : `${rawApiUrl}/api/ocena`
    : "/api/ocena";

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lat,
      lon,
      data_analizy: dataAnalizy,
      uprawa: uprawa ?? null,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    let message = `Błąd zapytania (${response.status})`;
    try {
      const body = JSON.parse(errorText);
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      if (errorText) message += `: ${errorText.slice(0, 200)}`;
    }
    throw new Error(message);
  }

  return response.json() as Promise<OcenaWilgotnosciResponse>;
}

export function useOcenaWilgotnosci(parametry: ParametryOceny) {
  return useQuery({
    queryKey: [
      "ocena-wilgotnosci",
      parametry.lat,
      parametry.lon,
      parametry.dataAnalizy,
      parametry.uprawa,
    ],
    queryFn: () => pobierzOcene(parametry),
    enabled: parametry.enabled ?? false,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
