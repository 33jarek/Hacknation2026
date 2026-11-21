import { useQuery } from "@tanstack/react-query";

export type PunktWilgotnosci = {
  data: string;
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

export type OcenaWilgotnosciResponse = {
  status: "success";
  lokalizacja: {
    lat: number;
    lon: number;
  };
  wynik: Record<string, unknown>;
  wykresy: {
    szereg_czasowy: PunktWilgotnosci[];
    regresja: {
      dostepna: boolean;
      r2: number | null;
      slope: number | null;
      intercept: number | null;
      punkty: PunktRegresji[];
      linia: PunktLiniiRegresji[];
    };
  };
};

type ParametryOceny = {
  lat: number;
  lon: number;
  dataAnalizy: string;
};

async function pobierzOcene({
  lat,
  lon,
  dataAnalizy,
}: ParametryOceny): Promise<OcenaWilgotnosciResponse> {
  const response = await fetch("http://127.0.0.1:8000/ocena", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lat,
      lon,
      data_analizy: dataAnalizy,
    }),
  });

  if (!response.ok) {
    throw new Error("Nie udało się pobrać danych");
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
    ],
    queryFn: () => pobierzOcene(parametry),
  });
}
