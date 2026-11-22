import type { OcenaAI } from "@Hooks/useOcenaWilgoci";
import { Card, Stat } from "./Card";

type Props = { ocena?: OcenaAI; className?: string };

const fmt = (value: number | null | undefined, unit: string) =>
  value == null ? "–" : `${value.toFixed(1)}${unit}`;

export const WeatherPlaceholder = ({ ocena, className = "" }: Props) => {
  const pogoda = ocena?.pogoda;
  return (
    <Card title="Warunki przed dniem analizy" className={className}>
      <div className="grid grid-cols-3 gap-4">
        <Stat value={fmt(pogoda?.temperatura_srednia_c, "°C")} label="śr. temp. maks., 14 dni" />
        <Stat value={fmt(pogoda?.opady_30_dni_mm, " mm")} label="opady, 30 dni" />
        <Stat value={fmt(pogoda?.wilgotnosc_gleby_pct, "%")} label="woda w glebie 0–100 cm" />
      </div>
    </Card>
  );
};
