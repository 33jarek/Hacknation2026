import { useMemo } from "react";
import { defineChart, lineY } from "@tanstack/charts";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { scalePoint } from "@tanstack/charts/scales/point";
import { tooltip } from "@tanstack/charts/tooltip";
import { Chart } from "@tanstack/charts/react";

type Punkt = {
  etykieta: string;
  ocena: number | null;
  q10: number | null;
  q90: number | null;
  era5: number | null;
};

type Props = {
  dane: Punkt[];
};

export default function WykresWilgotnosci({ dane }: Props) {
  const definicja = useMemo(() => {
    const serie = dane.filter(
      (punkt) =>
        punkt.ocena !== null ||
        punkt.q10 !== null ||
        punkt.q90 !== null ||
        punkt.era5 !== null,
    );

    return defineChart({
      marks: [
        lineY(serie, {
          x: "etykieta",
          y: "ocena",
          stroke: "#1f5b46",
          strokeWidth: 2.5,
        }),
        lineY(serie, {
          x: "etykieta",
          y: "era5",
          stroke: "#acc649",
          strokeWidth: 2.5,
          points: true,
        }),
        lineY(serie, {
          x: "etykieta",
          y: "q10",
          stroke: "#b7cfa3",
          strokeWidth: 1,
          strokeDasharray: "3 4",
        }),
        lineY(serie, {
          x: "etykieta",
          y: "q90",
          stroke: "#b7cfa3",
          strokeWidth: 1,
          strokeDasharray: "3 4",
        }),
      ],
      scales: {
        x: {
          scale: () => scalePoint<string>().padding(0.15),
          axis: {
            label: "Dzień",
          },
        },
        y: {
          scale: scaleLinear,
          domain: [0, 100],
          nice: false,
          grid: true,
          axis: { label: "Percentyl wilgotności (0 = najsucho, 100 = najmokro)", ticks: { format: (value: number) => `${value}` } },
        },
      },
      tooltip,
    });
  }, [dane]);

  return (
    <div style={{ width: "100%" }}>
      <Chart
        definition={definicja}
        height={360}
        ariaLabel="Wykres wilgotności gleby z ostatnich 7 dni"
      />
    </div>
  );
}
