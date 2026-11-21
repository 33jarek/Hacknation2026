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

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  const [analysisDate, setAnalysisDate] = useState("2026-11-21");
  const ocena = useOcenaWilgotnosci({
    lat: 52.2297,
    lon: 21.0122,
    dataAnalizy: analysisDate,
  });

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
        <PlotSelector date={analysisDate} onDateChange={setAnalysisDate} />
        <div className="mt-4">
          <StatusCard />
        </div>
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(300px,0.7fr)]">
          <ForecastPlaceholder
            dane={ocena.data?.wykresy.szereg_czasowy}
            isLoading={ocena.isLoading}
            isError={ocena.isError}
          />
          <div className="grid gap-4">
            <WeatherPlaceholder />
            <ActionsCard />
          </div>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <CausesCard />
          <VulnerabilityCard />
        </div>
      </main>
      <Footer />
    </div>
  );
}
