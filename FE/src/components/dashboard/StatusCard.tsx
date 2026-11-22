import type { OcenaAI } from "@Hooks/useOcenaWilgoci";
import { Card, Stat } from "./Card";

type Props = { ocena?: OcenaAI };

const kolorTekstu = {
  green: "text-kowr-green",
  olive: "text-[#7f8f2a]",
  red: "text-red-700",
} as const;

const kolorRyzyka: Record<string, string> = {
  wysokie: "border-red-700",
  umiarkowane: "border-[#b5c23a]",
  niskie: "border-kowr-green",
  "nadmiar wody": "border-kowr-green",
};

export const StatusCard = ({ ocena }: Props) => {
  if (!ocena) {
    return (
      <Card>
        <p className="text-sm text-kowr-gray">
          Wskaż lokalizację, wybierz datę i kliknij <strong className="text-kowr-text">Analizuj</strong>.
        </p>
      </Card>
    );
  }

  const s = ocena.sugestia;
  const kolorStanu = ocena.percentyl < 30 ? kolorTekstu.red : kolorTekstu.green;

  return (
    <Card bodyClassName="grid gap-5">
      {/* Krok 1 – ocena modelu */}
      <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_auto_auto_auto] md:items-center md:gap-10">
        <div>
          <h2 className={`text-xl font-semibold ${kolorStanu}`}>{ocena.status}</h2>
          <p className="mt-1 text-sm text-kowr-gray">{ocena.summary}</p>
        </div>
        <Stat value={<span className={kolorStanu}>{ocena.percentyl.toFixed(0)}</span>} label="percentyl (0 sucho – 100 mokro)" />
        <Stat value={ocena.zakres} label="przedział Q10–Q90" />
        {ocena.prognoza_7d ? (
          <Stat
            value={`${ocena.prognoza_7d.ocena.toFixed(0)} (${ocena.prognoza_7d.q10.toFixed(0)}–${ocena.prognoza_7d.q90.toFixed(0)})`}
            label={`prognoza na ${new Date(`${ocena.prognoza_7d.data}T12:00:00`).toLocaleDateString("pl-PL", { day: "numeric", month: "short" })}`}
          />
        ) : (
          <Stat
            value={ocena.zmiana_7d == null ? "–" : `${ocena.zmiana_7d > 0 ? "+" : ""}${ocena.zmiana_7d.toFixed(0)}`}
            label="zmiana w 7 dni"
          />
        )}
      </div>

      {/* Krok 2 – sugestia dla uprawy, wynikająca z oceny */}
      {s && (
        <div className={`border-l-2 pl-4 ${kolorRyzyka[s.ryzyko] ?? "border-kowr-border"}`}>
          <p className="text-sm font-medium text-kowr-text">{s.title}</p>
          <p className="mt-1 text-sm text-kowr-gray">{s.detail}</p>
          <p className="mt-1 text-xs text-kowr-gray/80">Na podstawie: {s.evidence}</p>
        </div>
      )}
    </Card>
  );
};
