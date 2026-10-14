import { useEffect, useRef } from "react";
import {
  AreaSeries,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  useLightweightChart,
  safeRemoveSeries,
} from "../../hooks/useLightweightChart";
import { chartRows, rowAtPin, useChartCutoff } from "../../hooks/useChartData";
import { useMarketStore } from "../../store/marketStore";
import { plainDate } from "../../../../shared/plainDate";
import { StatusMark } from "../reading/StatusMark";

export function ScoreChart({ fullSpan = false }: { fullSpan?: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chart = useLightweightChart(containerRef);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const history = useMarketStore((s) => s.scoreHistory);
  const cutoff = useChartCutoff();
  const shown = chartRows(history, cutoff, fullSpan);

  useEffect(() => {
    if (!chart) return;

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#0072B2",
      topColor: "rgba(0, 114, 178, 0.18)",
      bottomColor: "rgba(0, 114, 178, 0.02)",
      lineWidth: 2,
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 100 },
      }),
    });
    series.createPriceLine({
      price: 40,
      color: "#5C5E62",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: "Warming",
    });
    series.createPriceLine({
      price: 70,
      color: "#C2410C",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: "Stretched",
    });
    seriesRef.current = series;

    return () => {
      seriesRef.current = null;
      safeRemoveSeries(chart, series);
    };
  }, [chart]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series || !chart) return;
    series.setData(
      shown.map((d) => ({
        time: d.time as UTCTimestamp,
        value: d.value,
      }))
    );
    chart.timeScale().fitContent();
  }, [chart, shown]);

  const first = shown[0];
  const last = shown[shown.length - 1];
  const pinned = rowAtPin(shown, fullSpan ? cutoff : null);
  const when = (time: number) =>
    plainDate(new Date(time * 1000).toISOString().slice(0, 10));
  const caption = !last
    ? "The series are still loading."
    : fullSpan && first
      ? pinned && pinned.time !== last.time
        ? `This chart runs from ${when(first.time)} through ${when(last.time)}. The week page is pinned at ${when(pinned.time)}, where heat is ${pinned.value.toFixed(1)}.`
        : `This chart runs from ${when(first.time)} through ${when(last.time)}. Heat on ${when(last.time)} is ${last.value.toFixed(1)}.`
      : `Heat on ${when(last.time)} is ${last.value.toFixed(1)}.`;

  return (
    <div className="score-chart-wrap">
      <p className="chart-caption">{caption}</p>
      <div ref={containerRef} className="chart-container" />
      <div className="score-chart-legend">
        <span className="legend-item">
          <StatusMark word="Quiet" />
          Quiet, under 40
        </span>
        <span className="legend-item">
          <StatusMark word="Warming" />
          Warming, from 40
        </span>
        <span className="legend-item">
          <StatusMark word="Stretched" />
          Stretched, from 70
        </span>
      </div>
    </div>
  );
}
