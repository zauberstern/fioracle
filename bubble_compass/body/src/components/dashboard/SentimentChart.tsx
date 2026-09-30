import { useEffect, useRef } from "react";
import {
  BaselineSeries,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  useLightweightChart,
  safeRemoveSeries,
} from "../../hooks/useLightweightChart";
import { sliceByCutoff, useChartCutoff } from "../../hooks/useChartData";
import { useMarketStore } from "../../store/marketStore";

export function SentimentChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chart = useLightweightChart(containerRef);
  const seriesRef = useRef<ISeriesApi<"Baseline"> | null>(null);
  const history = useMarketStore((s) => s.sentimentHistory);
  const cutoff = useChartCutoff();

  useEffect(() => {
    if (!chart) return;

    const series = chart.addSeries(BaselineSeries, {
      baseValue: { type: "price", price: 0 },
      topLineColor: "#56B4E9",
      topFillColor1: "rgba(86, 180, 233, 0.28)",
      topFillColor2: "rgba(86, 180, 233, 0.02)",
      bottomLineColor: "#D55E00",
      bottomFillColor1: "rgba(213, 94, 0, 0.02)",
      bottomFillColor2: "rgba(213, 94, 0, 0.28)",
      lineWidth: 2,
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
      sliceByCutoff(history, cutoff).map((d) => ({
        time: d.time as UTCTimestamp,
        value: d.value,
      }))
    );
    chart.timeScale().fitContent();
  }, [chart, history, cutoff]);

  return <div ref={containerRef} className="chart-container" />;
}
