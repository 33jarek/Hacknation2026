import WykresWilgotnosci from "@Components/dashboard/Charts";
import type { PunktWilgotnosci } from "@Hooks/useOcenaWilgoci";

type Props = {
  dane?: PunktWilgotnosci[];
  isLoading: boolean;
  isError: boolean;
  isFallback?: boolean;
};

export const ForecastPlaceholder = ({ dane = [], isLoading, isError, isFallback = false }: Props) => {
  // ostatnie 7 dni kończące się na dniu analizy
  const tydzien = dane.slice(-7).map((p) => ({
    ...p,
    etykieta: new Date(`${p.data}T12:00:00`).toLocaleDateString("pl-PL", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
    }),
  }));
  const od = tydzien[0]?.data;
  const doDnia = tydzien[tydzien.length - 1]?.data;
  const fmt = (d: string) =>
    new Date(`${d}T12:00:00`).toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric" });
  return (
    <section className="rounded-2xl border border-kowr-border bg-kowr-white p-5">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-kowr-gray">Ostatnie 7 dni</p>
          <h2 className="mt-1 text-lg font-bold text-kowr-text">
            Wilgotność gleby dzień po dniu
            {od && doDnia && (
              <span className="ml-2 font-normal text-kowr-gray">
                {fmt(od)} – {fmt(doDnia)}
              </span>
            )}
          </h2>
        </div>
        <span className="rounded-full bg-kowr-sage/30 px-3 py-1 text-[11px] font-semibold text-kowr-forest">
          Model AI + ERA5
        </span>
      </div>
      <div className="relative min-h-72 rounded-xl border border-kowr-sage/60 bg-kowr-background px-2 py-3">
        {isFallback && !isLoading && !isError && (
          <div className="mx-3 mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Zewnętrzne źródła danych są chwilowo niedostępne. Wykres pokazuje ocenę rezerwową.
          </div>
        )}
        {isLoading ? (
          <div className="flex center min-h-64 text-sm text-kowr-gray">Liczenie prognozy…</div>
        ) : isError ? (
          <div className="flex center min-h-64 text-center text-sm text-kowr-gray">
            Nie udało się pobrać danych z modelu.
          </div>
        ) : tydzien.length ? (
          <>
            <div className="mb-1 flex flex-wrap justify-end gap-4 px-3 text-[10px] text-kowr-gray">
              <span className="flex items-center gap-1"><i className="h-0.5 w-4 bg-kowr-forest" />Ocena modelu</span>
              <span className="flex items-center gap-1"><i className="h-0.5 w-4 bg-kowr-olive" />ERA5 – percentyl</span>
              <span className="flex items-center gap-1"><i className="h-0.5 w-4 bg-kowr-sage" />Zakres Q10–Q90</span>
            </div>
            <WykresWilgotnosci dane={tydzien} />
            <p className="px-3 pt-1 text-[11px] leading-relaxed text-kowr-gray">
              Wykres pokazuje <strong>percentyl</strong> – jak wilgotna jest gleba na tle tej samej pory roku
              z ostatnich 10 lat (50 = typowo). To inna wielkość niż „woda w glebie” w karcie Pogoda
              (objętościowa zawartość wody, zwykle 10–45%).
            </p>
          </>
        ) : (
          <div className="flex center min-h-64 text-sm text-kowr-gray">Brak danych dla ostatnich 7 dni.</div>
        )}
      </div>
    </section>
  );
};
