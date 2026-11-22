import type { OcenaAI } from "@Hooks/useOcenaWilgoci";

type Props = { ocena?: OcenaAI };

export const StatusCard = ({ ocena }: Props) => {
  const status = ocena?.status ?? "Ładowanie oceny modelu";
  const summary = ocena?.summary ?? "Ocena zostanie uzupełniona po pobraniu danych.";
  const percentyl = ocena?.percentyl;
  const zakres = ocena?.zakres ?? "brak przedziału";
  const percentClass = ocena?.kolor === "green"
    ? "text-kowr-green"
    : ocena?.kolor === "olive"
      ? "text-kowr-olive"
      : "text-red-700";
  return (
    <section className="grid min-h-52 overflow-hidden rounded-2xl border border-kowr-border bg-kowr-white md:grid-cols-[1fr_220px_260px]">
      <div className="flex flex-col justify-center p-6 md:p-8">
        <p className="mb-3 text-xs font-bold uppercase tracking-widest text-kowr-gray">Stan działki</p>
        <div className="flex items-center gap-3">
          <div className="flex center size-12 shrink-0 rounded-full bg-kowr-beige text-kowr-forest">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M12 2.8S5.5 10 5.5 15a6.5 6.5 0 0 0 13 0C18.5 10 12 2.8 12 2.8Z" />
            </svg>
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-kowr-text">{status}</h2>
            <p className="mt-1 text-sm text-kowr-gray">{summary}</p>
          </div>
        </div>
      </div>
      <div className="flex center flex-col border-t border-kowr-border bg-kowr-background px-6 py-5 md:border-l md:border-t-0">
        <span className="text-xs text-kowr-gray">Percentyl wobec tej pory roku</span>
        <strong className={`mt-1 text-4xl font-bold ${percentClass}`}>{percentyl?.toFixed(1) ?? "–"}</strong>
        <span className="mt-1 text-center text-xs text-kowr-gray">0 = najsucho, 100 = najmokro<br />(10 lat)</span>
      </div>
      <div className="flex flex-col justify-center border-t border-kowr-border px-6 py-5 md:border-l md:border-t-0">
        <span className="text-xs text-kowr-gray">Przedział niepewności</span>
        <strong className="mt-1 text-xl font-bold text-kowr-text">{zakres}</strong>
        <span className="mt-2 text-[11px] leading-4 text-kowr-gray">Percentyl mieści się w tym zakresie z 80% pewnością (Q10–Q90)</span>
      </div>
    </section>
  );
};
