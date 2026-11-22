import type { OcenaAI } from "@Hooks/useOcenaWilgoci";

type Props = { ocena?: OcenaAI };

export const WeatherPlaceholder = ({ ocena }: Props) => {
  const pogoda = ocena?.pogoda;
  const formatValue = (value: number | null | undefined, unit: string) =>
    value == null ? "brak danych" : `${value.toFixed(1)}${unit}`;
  const weatherItems = [
    { label: "Śr. temp. maks. (14 dni)", value: formatValue(pogoda?.temperatura_srednia_c, "°C"), icon: "T" },
    { label: "Opady 30 dni", value: formatValue(pogoda?.opady_30_dni_mm, " mm"), icon: "O" },
    { label: "Woda w glebie 0–100 cm (obj.)", value: formatValue(pogoda?.wilgotnosc_gleby_pct, "%"), icon: "W" },
  ];
  return (
    <section className="rounded-2xl border border-kowr-border bg-kowr-white p-5">
      <div className="mb-4">
        <p className="text-xs font-bold uppercase tracking-widest text-kowr-gray">Warunki</p>
        <h2 className="mt-1 text-lg font-bold text-kowr-text">Przed dniem analizy</h2>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {weatherItems.map((item) => (
          <div key={item.label} className="rounded-xl border border-kowr-border bg-kowr-background px-2 py-4 text-center">
            <span className="flex center mx-auto mb-2 size-7 rounded-full bg-kowr-white text-xs font-bold text-kowr-forest">{item.icon}</span>
            <strong className="block text-base text-kowr-text">{item.value}</strong>
            <span className="mt-1 block text-[10px] text-kowr-gray">{item.label}</span>
          </div>
        ))}
      </div>
      {ocena && !pogoda && (
        <div className="mt-3 rounded-xl border border-dashed border-kowr-sage bg-kowr-background px-3 py-4">
          <svg
            viewBox="0 0 420 88"
            role="img"
            aria-label="Brak danych pogodowych"
            className="h-20 w-full"
          >
            <line x1="32" y1="58" x2="388" y2="58" stroke="#9cae92" strokeWidth="2" />
            {[32, 121, 210, 299, 388].map((x) => (
              <line key={x} x1={x} y1="54" x2={x} y2="62" stroke="#9cae92" strokeWidth="2" />
            ))}
            <text x="210" y="34" textAnchor="middle" fill="#69766f" fontSize="12">
              Brak danych pogodowych
            </text>
          </svg>
        </div>
      )}
    </section>
  );
};
