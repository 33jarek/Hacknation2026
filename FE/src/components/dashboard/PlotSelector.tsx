import { useRef, useState, type FormEvent } from "react";
import { MapaPolski } from "./MapaPolski";
import {
  lokalizacjaZAdresu,
  lokalizacjaZDzialki,
  lokalizacjaZPunktu,
  parsujWspolrzedne,
  wPolsce,
  type TrybWyszukiwania,
  type WybranaLokalizacja,
} from "@Hooks/lokalizacja";

export const UPRAWY = [
  { key: "zboza-ozime",    label: "Zboża ozime" },
  { key: "zboza-jare",     label: "Zboża jare" },
  { key: "kukurydza",      label: "Kukurydza" },
  { key: "rzepak",         label: "Rzepak i rzepik" },
  { key: "burak-cukrowy",  label: "Burak cukrowy" },
  { key: "ziemniaki",      label: "Ziemniaki" },
  { key: "straczkowe",     label: "Rośliny strączkowe" },
  { key: "uzytki-zielone", label: "Użytki zielone" },
  { key: "drzewa-owocowe", label: "Drzewa i krzewy owocowe" },
] as const;

const TRYBY: { key: TrybWyszukiwania; label: string; placeholder: string }[] = [
  { key: "adres", label: "Adres", placeholder: "np. Wiejska 4, Warszawa lub Kłodzko" },
  { key: "dzialka", label: "Nr działki", placeholder: "np. 141201_1.0001.6509 lub Krzyki 33/1" },
  { key: "wspolrzedne", label: "Współrzędne", placeholder: "np. 52.2297, 21.0122" },
];

type PlotSelectorProps = {
  lokalizacja: WybranaLokalizacja;
  uprawa: string;
  date: string;
  onLokalizacjaChange: (lok: WybranaLokalizacja) => void;
  onUpravaChange: (uprawa: string) => void;
  onDateChange: (date: string) => void;
  onAnalyze: () => void;
  isAnalyzing?: boolean;
  onReport: () => void;
  canReport: boolean;
  isReporting?: boolean;
};

// zakres dat: ostatnie 10 lat do dziś (czas lokalny)
const isoLokalnie = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const DZIS = new Date();
const DATA_MAX = isoLokalnie(DZIS);
const DATA_MIN = isoLokalnie(new Date(DZIS.getFullYear() - 10, DZIS.getMonth(), DZIS.getDate()));

const inputCls =
  "h-10 w-full min-w-0 rounded-md border border-kowr-border bg-kowr-white px-3 text-sm font-normal text-kowr-text outline-none focus:border-kowr-forest";
const labelCls = "flex h-5 items-end text-xs text-kowr-gray";

export const PlotSelector = ({
  lokalizacja,
  uprawa,
  date,
  onLokalizacjaChange,
  onUpravaChange,
  onDateChange,
  onAnalyze,
  isAnalyzing = false,
  onReport,
  canReport,
  isReporting = false,
}: PlotSelectorProps) => {
  const [tryb, setTryb] = useState<TrybWyszukiwania>("adres");
  const [zapytanie, setZapytanie] = useState("");
  const [szukam, setSzukam] = useState(false);
  const [blad, setBlad] = useState<string | null>(null);
  const [focusKey, setFocusKey] = useState(0);
  const seq = useRef(0);

  const aktywnyTryb = TRYBY.find((t) => t.key === tryb)!;

  async function wykonaj(fn: () => Promise<WybranaLokalizacja>, zrodlo: "mapa" | "wyszukiwanie") {
    const id = ++seq.current;
    setSzukam(true);
    setBlad(null);
    try {
      const wynik = await fn();
      if (id !== seq.current) return; // nowsze zapytanie w toku
      onLokalizacjaChange({ ...wynik, zrodlo });
      if (zrodlo === "wyszukiwanie") setFocusKey((k) => k + 1);
    } catch (e) {
      if (id !== seq.current) return;
      setBlad(e instanceof Error ? e.message : "Nie udało się wyszukać lokalizacji");
    } finally {
      if (id === seq.current) setSzukam(false);
    }
  }

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    const q = zapytanie.trim();
    if (!q) {
      setBlad("Wpisz, czego szukać");
      return;
    }
    if (tryb === "adres") {
      void wykonaj(() => lokalizacjaZAdresu(q), "wyszukiwanie");
    } else if (tryb === "dzialka") {
      void wykonaj(() => lokalizacjaZDzialki(q), "wyszukiwanie");
    } else {
      const wsp = parsujWspolrzedne(q);
      if (!wsp) {
        setBlad("Podaj współrzędne w formacie: 52.2297, 21.0122");
        return;
      }
      if (!wPolsce(wsp[0], wsp[1])) {
        setBlad("Współrzędne leżą poza Polską");
        return;
      }
      void wykonaj(() => lokalizacjaZPunktu(wsp[0], wsp[1]), "wyszukiwanie");
    }
  }

  function handleMapPick(lat: number, lon: number) {
    if (!wPolsce(lat, lon)) {
      setBlad("Wybierz punkt na terenie Polski");
      return;
    }
    // natychmiastowy feedback – marker przesuwa się od razu
    onLokalizacjaChange({
      lat,
      lon,
      label: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
      parcel: null,
      parcel_error: null,
      zrodlo: "mapa",
    });
    void wykonaj(() => lokalizacjaZPunktu(lat, lon), "mapa");
  }

  const p = lokalizacja.parcel;

  return (
    <section className="rounded-lg border border-kowr-border bg-kowr-white p-5">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_200px_170px_auto] lg:items-end">
        {/* Wyszukiwarka lokalizacji */}
        <form onSubmit={handleSearch} className="grid gap-1.5">
          <div className={labelCls}>
            <div role="tablist" className="flex gap-4">
              {TRYBY.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  role="tab"
                  aria-selected={tryb === t.key}
                  onClick={() => {
                    setTryb(t.key);
                    setBlad(null);
                  }}
                  className={`border-b pb-px transition-colors ${
                    tryb === t.key
                      ? "border-kowr-forest font-medium text-kowr-forest"
                      : "border-transparent hover:text-kowr-text"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={zapytanie}
              onChange={(e) => setZapytanie(e.target.value)}
              placeholder={aktywnyTryb.placeholder}
              aria-label={aktywnyTryb.label}
              className={`${inputCls} min-w-0 flex-1`}
            />
            <button
              type="submit"
              disabled={szukam}
              className="h-10 shrink-0 rounded-md border border-kowr-border px-4 text-sm text-kowr-text transition-colors hover:border-kowr-forest hover:text-kowr-forest disabled:cursor-wait disabled:opacity-60"
            >
              {szukam ? "Szukam…" : "Szukaj"}
            </button>
          </div>
        </form>

        {/* Uprawa */}
        <label className="grid gap-1.5">
          <span className={labelCls}>Uprawa</span>
          <select value={uprawa} onChange={(e) => onUpravaChange(e.target.value)} className={inputCls}>
            <option value="">Wybierz uprawę</option>
            {UPRAWY.map((u) => (
              <option key={u.key} value={u.key}>{u.label}</option>
            ))}
          </select>
        </label>

        {/* Data */}
        <label className="grid gap-1.5">
          <span className={labelCls}>Data analizy</span>
          <input
            type="date"
            value={date}
            min={DATA_MIN}
            max={DATA_MAX}
            onChange={(e) => onDateChange(e.target.value)}
            className={inputCls}
          />
        </label>

        {/* Przyciski */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onAnalyze}
            disabled={isAnalyzing || szukam}
            className="h-10 w-full rounded-md bg-kowr-forest px-5 text-sm font-medium text-kowr-white transition-colors hover:bg-kowr-green disabled:cursor-wait disabled:opacity-70 lg:w-auto"
          >
            {isAnalyzing ? "Analizowanie…" : "Analizuj"}
          </button>
          <button
            type="button"
            onClick={onReport}
            disabled={!canReport || isReporting || isAnalyzing}
            title={canReport ? "Pobierz raport z analizy w formacie PDF" : "Najpierw wykonaj analizę"}
            className="h-10 w-full whitespace-nowrap rounded-md bg-kowr-olive px-4 text-sm font-medium text-kowr-text transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50 lg:w-auto"
          >
            {isReporting ? "Generowanie…" : "Pobierz raport PDF"}
          </button>
        </div>
      </div>

      {blad && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {blad}
        </p>
      )}

      {/* Mapa + informacje o wybranej lokalizacji */}
      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="relative h-90 overflow-hidden rounded-md border border-kowr-border">
            <MapaPolski
              lat={lokalizacja.lat}
              lon={lokalizacja.lon}
              parcelGeometry={p?.geometry ?? null}
              focusKey={focusKey}
              onPick={handleMapPick}
            />
        </div>

        <aside className="flex flex-col gap-3 text-sm">
          <div className="min-w-0">
            <p className="font-medium leading-snug text-kowr-text" title={lokalizacja.label}>
              {szukam ? "Wyszukiwanie…" : lokalizacja.label}
            </p>
            <p className="mt-0.5 text-xs tabular-nums text-kowr-gray">
              {lokalizacja.lat.toFixed(5)}, {lokalizacja.lon.toFixed(5)}
            </p>
          </div>

          {p ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t border-kowr-border pt-3 text-xs">
              <dt className="text-kowr-gray">Działka</dt>
              <dd className="font-medium text-kowr-text">{p.numer ?? "—"}</dd>
              <dt className="text-kowr-gray">Identyfikator</dt>
              <dd className="break-all text-kowr-text">{p.id}</dd>
              {p.obreb && (
                <>
                  <dt className="text-kowr-gray">Obręb</dt>
                  <dd className="text-kowr-text">{p.obreb}</dd>
                </>
              )}
              {p.gmina && (
                <>
                  <dt className="text-kowr-gray">Gmina</dt>
                  <dd className="text-kowr-text">{p.gmina}</dd>
                </>
              )}
              {p.powiat && (
                <>
                  <dt className="text-kowr-gray">Powiat</dt>
                  <dd className="text-kowr-text">{p.powiat}</dd>
                </>
              )}
              {p.powierzchnia_ha != null && (
                <>
                  <dt className="text-kowr-gray">Powierzchnia</dt>
                  <dd className="text-kowr-text">{p.powierzchnia_ha} ha</dd>
                </>
              )}
            </dl>
          ) : lokalizacja.parcel_error ? (
            <p className="border-t border-kowr-border pt-3 text-xs leading-relaxed text-kowr-gray">
              Nie udało się pobrać obrysu działki ({lokalizacja.parcel_error.toLowerCase()}). Analiza działa
              dla wskazanego punktu.
            </p>
          ) : (
            <p className="border-t border-kowr-border pt-3 text-xs leading-relaxed text-kowr-gray">
              Kliknij na mapie albo wyszukaj adres, numer działki lub współrzędne.
            </p>
          )}
        </aside>
      </div>
    </section>
  );
};
