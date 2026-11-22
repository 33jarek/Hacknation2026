import { Header } from "@/components/header/Header";
import { Footer } from "@Components/footer/Footer";
import { ActionsCard } from "@/components/dashboard/ActionsCard";
import { CausesCard } from "@/components/dashboard/CausesCard";
import { ForecastPlaceholder } from "@/components/dashboard/ForecastPlaceholder";
import { PlotSelector } from "@/components/dashboard/PlotSelector";
import { StatusCard } from "@/components/dashboard/StatusCard";
import { WeatherPlaceholder } from "@/components/dashboard/WeatherPlaceholder";
import { VulnerabilityCard } from "@/components/dashboard/VulnerabilityCard";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useOcenaWilgotnosci } from "@Hooks/useOcenaWilgoci";
import type { WybranaLokalizacja } from "@Hooks/lokalizacja";

export const Route = createFileRoute("/")(
{
  component: Index,
});

function Index() {
  const [lokalizacja, setLokalizacja] = useState<WybranaLokalizacja>({
    lat: 52.2297,
    lon: 21.0122,
    label: "Warszawa",
    parcel: null,
    parcel_error: null,
    zrodlo: "start",
  });
  const [uprawa, setUprawa] = useState("");
  const [analysisDate, setAnalysisDate] = useState("2024-07-15");
  // Po pierwszym "Analizuj" każda zmiana działki/daty/uprawy odświeża analizę sama.
  const [autoAnaliza, setAutoAnaliza] = useState(false);

  const ocena = useOcenaWilgotnosci({
    lat: lokalizacja.lat,
    lon: lokalizacja.lon,
    dataAnalizy: analysisDate,
    uprawa,
    enabled: autoAnaliza,
  });

  function handleAnalyze() {
    if (!autoAnaliza) setAutoAnaliza(true);
    else void ocena.refetch();
  }

  return (
    <div className="min-h-screen bg-kowr-background text-kowr-text">
      <Header />
      <main className="mx-auto max-w-360 px-5 py-6 md:px-8">
        <div className="mb-5">
          <p className="text-xs font-bold uppercase tracking-widest text-kowr-gray">
            Panel gospodarstwa
          </p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-kowr-text">
            Stan i prognoza działki
          </h2>
        </div>
        <PlotSelector
          lokalizacja={lokalizacja}
          uprawa={uprawa}
          date={analysisDate}
          onLokalizacjaChange={setLokalizacja}
          onUpravaChange={setUprawa}
          onDateChange={setAnalysisDate}
          onAnalyze={handleAnalyze}
          isAnalyzing={ocena.isFetching}
        />

        {ocena.isError && (
          <div
            role="alert"
            className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            <span>
              <strong>Analiza nie powiodła się.</strong> {ocena.error.message}
            </span>
            <button
              type="button"
              onClick={() => void ocena.refetch()}
              className="shrink-0 rounded-lg border border-red-300 px-3 py-1 text-xs font-semibold hover:bg-red-100"
            >
              Spróbuj ponownie
            </button>
          </div>
        )}

        {/* Status */}
        <div className="mt-4">
          <StatusCard ocena={ocena.data?.ocena_ai} />
        </div>

        {/* Wykres + Pogoda + Rekomendacje */}
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(300px,0.7fr)]">
          <ForecastPlaceholder
            dane={ocena.data?.wykresy.szereg_czasowy}
            isLoading={ocena.isLoading || ocena.isFetching}
            isError={ocena.isError}
            isFallback={ocena.data?.status === "fallback"}
          />
          <div className="grid gap-4">
            <WeatherPlaceholder ocena={ocena.data?.ocena_ai} />
            <ActionsCard recommendations={ocena.data?.rekomendacje} />
          </div>
        </div>

        {/* Przyczyny + Historia */}
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <CausesCard causes={ocena.data?.ocena_ai.causes} />
          <VulnerabilityCard ocena={ocena.data?.ocena_ai} />
        </div>

        {/* Uprawa badge */}
        {ocena.data?.ocena_ai.uprawa && (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-kowr-border bg-kowr-white px-4 py-3">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-kowr-forest" aria-hidden="true">
              <path d="M12 22V12M12 12C12 7 7 2 2 2c0 5 5 8 10 10ZM12 12c0-5 5-10 10-10-5 0-10 5-10 10Z" />
            </svg>
            <span className="text-sm text-kowr-text">
              Analiza dostosowana do uprawy:{" "}
              <strong className="text-kowr-forest">{ocena.data.ocena_ai.uprawa}</strong>
            </span>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
