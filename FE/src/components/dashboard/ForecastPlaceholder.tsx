import WykresWilgotnosci from "@Components/dashboard/Charts";
import type { PunktWilgotnosci } from "@Hooks/useOcenaWilgoci";

type Props = {
  dane?: PunktWilgotnosci[];
  isLoading: boolean;
  isError: boolean;
};

export const ForecastPlaceholder = ({ dane = [], isLoading, isError }: Props) => {
  return (
    <section className="rounded-2xl border border-kowr-border bg-kowr-white p-5">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-kowr-gray">Prognoza</p>
          <h2 className="mt-1 text-lg font-bold text-kowr-text">Wilgotność i opady</h2>
        </div>
        <span className="rounded-full bg-kowr-sage/30 px-3 py-1 text-[11px] font-semibold text-kowr-forest">
          Python / Backend
        </span>
      </div>
      <div className="relative min-h-72 rounded-xl border border-kowr-sage/60 bg-kowr-background px-2 py-3">
        {isLoading ? (
          <div className="flex center min-h-64 text-sm text-kowr-gray">Liczenie prognozy…</div>
        ) : isError ? (
          <div className="flex center min-h-64 text-center text-sm text-kowr-gray">
            Nie udało się pobrać danych z modelu.
          </div>
        ) : dane.length ? (
          <>
            <div className="mb-1 flex flex-wrap justify-end gap-4 px-3 text-[10px] text-kowr-gray">
              <span className="flex items-center gap-1"><i className="h-0.5 w-4 bg-kowr-forest" />Ocena modelu</span>
              <span className="flex items-center gap-1"><i className="h-0.5 w-4 bg-kowr-olive" />ERA5 percentyl</span>
              <span className="flex items-center gap-1"><i className="h-0.5 w-4 bg-kowr-sage" />Zakres Q10–Q90</span>
            </div>
            <WykresWilgotnosci dane={dane} />
          </>
        ) : (
          <div className="flex center min-h-64 text-sm text-kowr-gray">Brak danych w szeregu czasowym.</div>
        )}
      </div>
    </section>
  );
};
