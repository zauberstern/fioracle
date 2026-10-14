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
import { chartRows, useChartCutoff } from "../../hooks/useChartData";
import { useMarketStore } from "../../store/marketStore";

export function SentimentChart({ fullSpan = false }: { fullSpan?: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chart = useLightweightChart(containerRef);
  const seriesRef = useRef<ISeriesApi<"Baseline"> | null>(null);
  const history = useMarketStore((s) => s.sentimentHistory);
  const asset = useMarketStore((s) => s.currentAsset);
  const unavailable = useMarketStore(
    (s) => s.getAssetState(asset).sentiment.unavailable ?? true
  );
  const cutoff = useChartCutoff();

  useEffect(() => {
    if (!chart) return;

    const series = chart.addSeries(BaselineSeries, {
      baseValue: { type: "price", price: 0 },
      topLineColor: "#0072B2",
      topFillColor1: "rgba(0, 114, 178, 0.16)",
      topFillColor2: "rgba(0, 114, 178, 0.02)",
      bottomLineColor: "#C2410C",
      bottomFillColor1: "rgba(194, 65, 12, 0.02)",
      bottomFillColor2: "rgba(194, 65, 12, 0.16)",
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
      chartRows(history, cutoff, fullSpan).map((d) => ({
        time: d.time as UTCTimestamp,
        value: d.value,
      }))
    );
    chart.timeScale().fitContent();
  }, [chart, history, cutoff, fullSpan]);

  if (unavailable || history.length === 0) {
    return (
      <div className="chart-container chart-empty" role="status">
        Sentiment unavailable (no headlines in this history).
      </div>
    );
  }

  return <div ref={containerRef} className="chart-container" />;
}
