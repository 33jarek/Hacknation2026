import { useMemo } from "react";
import { defineChart, lineY } from "@tanstack/charts";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { scalePoint } from "@tanstack/charts/scales/point";
import { tooltip } from "@tanstack/charts/tooltip";
import { Chart } from "@tanstack/charts/react";

type Punkt = {
  data: string;
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
          x: "data",
          y: "ocena",
          stroke: "#1f5b46",
          strokeWidth: 2.5,
          points: true,
        }),
        lineY(serie, {
          x: "data",
          y: "era5",
          stroke: "#acc649",
          strokeWidth: 2,
          strokeDasharray: "6 4",
        }),
        lineY(serie, {
          x: "data",
          y: "q10",
          stroke: "#b7cfa3",
          strokeWidth: 1,
          strokeDasharray: "3 4",
        }),
        lineY(serie, {
          x: "data",
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
            ticks: {
              format: (value: string) =>
                value ? new Date(`${value}T12:00:00`).toLocaleDateString("pl-PL", {
                  day: "2-digit",
                  month: "short",
                }) : "",
            },
          },
        },
        y: {
          scale: scaleLinear,
          domain: [0, 100],
          nice: false,
          grid: true,
          axis: { label: "Wilgotność gleby", ticks: { format: (value: number) => `${value}%` } },
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
        ariaLabel="Wykres oceny wilgotności gleby"
      />
    </div>
  );
}
