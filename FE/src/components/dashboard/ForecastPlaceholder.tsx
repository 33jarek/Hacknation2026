import WykresWilgotnosci from "@Components/dashboard/Charts";
import type { PunktWilgotnosci } from "@Hooks/useOcenaWilgoci";
import { Card } from "./Card";

type Props = {
  dane?: PunktWilgotnosci[];
  isLoading: boolean;
  isError: boolean;
  isFallback?: boolean;
  className?: string;
};

const fmtKrotko = (d: string) =>
  new Date(`${d}T12:00:00`).toLocaleDateString("pl-PL", { day: "numeric", month: "short", year: "numeric" });

export const ForecastPlaceholder = ({ dane = [], isLoading, isError, isFallback = false, className = "" }: Props) => {
  // ostatnie 7 dni kończące się na ostatnim ocenionym dniu (dla dat bieżących: ~6 dni przed analizą, opóźnienie ERA5)
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

  return (
    <Card
      title="Wilgotność gleby – ostatnie 7 dni"
      aside={od && doDnia ? `${fmtKrotko(od)} – ${fmtKrotko(doDnia)}` : undefined}
      className={className}
    >
      {isLoading ? (
        <div className="flex center h-90 text-sm text-kowr-gray">Liczenie…</div>
      ) : isError ? (
        <div className="flex center h-90 text-sm text-kowr-gray">Nie udało się pobrać danych z modelu.</div>
      ) : tydzien.length ? (
        <>
          {isFallback && (
            <p className="mb-2 text-xs text-amber-800">
              Zewnętrzne źródła danych są chwilowo niedostępne – pokazano ocenę rezerwową.
            </p>
          )}
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-kowr-gray">
            <span className="flex items-center gap-1.5"><i className="h-0.5 w-4 bg-kowr-forest" />ocena modelu</span>
            <span className="flex items-center gap-1.5"><i className="h-0.5 w-4 bg-kowr-olive" />ERA5</span>
            <span className="flex items-center gap-1.5"><i className="h-px w-4 border-t border-dashed border-kowr-gray" />przedział Q10–Q90</span>
          </div>
          <WykresWilgotnosci dane={tydzien} />
          <p className="mt-1 text-xs text-kowr-gray">
            Percentyl wilgotności na tle tej samej pory roku z ostatnich 10 lat (50 = typowo).
          </p>
        </>
      ) : (
        <div className="flex center h-90 text-sm text-kowr-gray">Wykres pojawi się po analizie.</div>
      )}
    </Card>
  );
};
