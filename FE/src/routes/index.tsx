import { Header } from "@/components/header/Header";
import { Footer } from "@Components/footer/Footer";
import { ActionsCard } from "@/components/dashboard/ActionsCard";
import { CausesCard } from "@/components/dashboard/CausesCard";
import { ForecastPlaceholder } from "@/components/dashboard/ForecastPlaceholder";
import { PlotSelector } from "@/components/dashboard/PlotSelector";
import { czyPoprawnaData, DATA_MIN, DATA_MAX } from "@/components/dashboard/zakresDat";
import { StatusCard } from "@/components/dashboard/StatusCard";
import { WeatherPlaceholder } from "@/components/dashboard/WeatherPlaceholder";
import { VulnerabilityCard } from "@/components/dashboard/VulnerabilityCard";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useOcenaWilgotnosci } from "@Hooks/useOcenaWilgoci";
import { pobierzRaportPdf, type WybranaLokalizacja } from "@Hooks/lokalizacja";

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
  const dataPoprawna = czyPoprawnaData(analysisDate);

  const ocena = useOcenaWilgotnosci({
    lat: lokalizacja.lat,
    lon: lokalizacja.lon,
    dataAnalizy: analysisDate,
    uprawa,
    enabled: autoAnaliza && dataPoprawna,
  });

  // Model ocenia najwyżej dzień sprzed ~6 dni (opóźnienie ERA5) – powiedz o tym wprost
  const wynik = ocena.data?.wynik as
    | { data_analizy?: string; dzien_ocenionych_danych?: string; braki_i_ograniczenia?: string[] }
    | undefined;
  const dzienOceniony =
    wynik?.dzien_ocenionych_danych && wynik.dzien_ocenionych_danych !== wynik.data_analizy
      ? wynik.dzien_ocenionych_danych
      : null;
  const braki = wynik?.braki_i_ograniczenia ?? [];

  const [raportTrwa, setRaportTrwa] = useState(false);
  const [raportBlad, setRaportBlad] = useState<string | null>(null);

  async function handleReport() {
    setRaportTrwa(true);
    setRaportBlad(null);
    try {
      await pobierzRaportPdf({ lokalizacja, dataAnalizy: analysisDate, uprawa });
    } catch (e) {
      setRaportBlad(e instanceof Error ? e.message : "Nie udało się pobrać raportu");
    } finally {
      setRaportTrwa(false);
    }
  }

  function handleAnalyze() {
    if (!dataPoprawna) return;
    if (!autoAnaliza) setAutoAnaliza(true);
    else void ocena.refetch();
  }

  return (
    <div className="min-h-screen bg-kowr-background text-kowr-text">
      <Header />
      <main className="mx-auto grid max-w-360 gap-4 px-5 py-6 md:px-8">
        <PlotSelector
          lokalizacja={lokalizacja}
          uprawa={uprawa}
          date={analysisDate}
          onLokalizacjaChange={setLokalizacja}
          onUpravaChange={setUprawa}
          onDateChange={setAnalysisDate}
          onAnalyze={handleAnalyze}
          isAnalyzing={ocena.isFetching}
          onReport={() => void handleReport()}
          canReport={ocena.isSuccess && !ocena.isFetching}
          isReporting={raportTrwa}
        />

        {!dataPoprawna && (
          <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Podaj pełną datę z zakresu {DATA_MIN} – {DATA_MAX}.
          </div>
        )}

        {ocena.isSuccess && (dzienOceniony || braki.length > 0) && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {dzienOceniony && (
              <p>
                Wyniki dotyczą dnia <strong>{dzienOceniony}</strong>, a nie wybranego {wynik?.data_analizy}. To
                ostatni dzień, dla którego są już dane pomiarowe.
              </p>
            )}
            {braki.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-xs">
                {braki.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {raportBlad && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            Nie udało się wygenerować raportu. {raportBlad}
          </div>
        )}

        {ocena.isError && (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            <span>Analiza nie powiodła się. {ocena.error.message}</span>
            <button
              type="button"
              onClick={() => void ocena.refetch()}
              className="shrink-0 rounded-md border border-red-300 px-3 py-1 text-xs font-medium hover:bg-red-100"
            >
              Spróbuj ponownie
            </button>
          </div>
        )}

        <StatusCard ocena={ocena.data?.ocena_ai} />

        <div className="grid gap-4 lg:grid-cols-3">
          <ForecastPlaceholder
            className="lg:col-span-2"
            dane={ocena.data?.wykresy.szereg_czasowy}
            isLoading={ocena.isLoading || ocena.isFetching}
            isError={ocena.isError}
            isFallback={ocena.data?.status === "fallback"}
          />
          <div className="grid gap-4 lg:grid-rows-2">
            <WeatherPlaceholder ocena={ocena.data?.ocena_ai} />
            <VulnerabilityCard ocena={ocena.data?.ocena_ai} />
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <CausesCard causes={ocena.data?.ocena_ai.causes} />
          <ActionsCard
            title="Rekomendacje retencyjne"
            recommendations={ocena.data?.ocena_ai.rekomendacje_retencyjne}
          />
          <ActionsCard
            title="Rekomendacje agrotechniczne"
            recommendations={ocena.data?.ocena_ai.rekomendacje_agrotechniczne}
          />
        </div>
      </main>
      <Footer />
    </div>
  );
}
