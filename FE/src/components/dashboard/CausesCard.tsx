import type { PrzyczynaAI } from "@Hooks/useOcenaWilgoci";

type Props = { causes?: PrzyczynaAI[] };

export const CausesCard = ({ causes = [] }: Props) => {
  return (
    <section className="rounded-2xl border border-kowr-border bg-kowr-white p-5">
      <p className="text-xs font-bold uppercase tracking-widest text-kowr-gray">Przyczyny</p>
      <h2 className="mt-1 text-lg font-bold text-kowr-text">Co wpływa na wilgotność</h2>
      <div className="mt-4 grid gap-2">
        {(causes.length ? causes : [{ title: "Analiza AI", value: "Ładowanie", detail: "Backend przygotowuje przyczyny na podstawie wyników modelu." }]).map((cause) => (
          <div key={cause.title} className="rounded-xl border border-kowr-border bg-kowr-background p-3">
            <div className="flex items-start justify-between gap-3">
              <strong className="text-sm text-kowr-text">{cause.title}</strong>
              <span className="text-right text-xs font-bold text-kowr-forest">{cause.value}</span>
            </div>
            <p className="mt-1 text-[11px] leading-4 text-kowr-gray">{cause.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
};
