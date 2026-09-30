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
import { sliceByCutoff, useChartCutoff } from "../../hooks/useChartData";
import { useMarketStore } from "../../store/marketStore";

export function ScoreChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chart = useLightweightChart(containerRef);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const history = useMarketStore((s) => s.scoreHistory);
  const cutoff = useChartCutoff();

  useEffect(() => {
    if (!chart) return;

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#56B4E9",
      topColor: "rgba(86, 180, 233, 0.35)",
      bottomColor: "rgba(86, 180, 233, 0.02)",
      lineWidth: 2,
    });
    series.createPriceLine({
      price: 40,
      color: "#E69F00",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: "Warming",
    });
    series.createPriceLine({
      price: 70,
      color: "#D55E00",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: "Hot",
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
