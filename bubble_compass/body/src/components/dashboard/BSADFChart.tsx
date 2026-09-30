import { useEffect, useRef } from "react";
import {
  HistogramSeries,
  LineSeries,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  useLightweightChart,
  safeRemoveSeries,
} from "../../hooks/useLightweightChart";
import { sliceByCutoff, useChartCutoff } from "../../hooks/useChartData";
import { useMarketStore } from "../../store/marketStore";

export function BSADFChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chart = useLightweightChart(containerRef);
  const statRef = useRef<ISeriesApi<"Line"> | null>(null);
  const cvRef = useRef<ISeriesApi<"Line"> | null>(null);
  const excessRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const history = useMarketStore((s) => s.bsadfHistory);
  const cutoff = useChartCutoff();

  useEffect(() => {
    if (!chart) return;

    const statSeries = chart.addSeries(LineSeries, {
      color: "#56B4E9",
      lineWidth: 2,
      title: "Stretch",
    });
    const cvSeries = chart.addSeries(LineSeries, {
      color: "#E69F00",
      lineWidth: 1,
      lineStyle: 2,
      title: "Line",
    });
    const excessSeries = chart.addSeries(HistogramSeries, {
      color: "#D55E00",
      priceScaleId: "excess",
    });
    chart.priceScale("excess").applyOptions({
      scaleMargins: { top: 0.7, bottom: 0 },
    });

    statRef.current = statSeries;
    cvRef.current = cvSeries;
    excessRef.current = excessSeries;

    return () => {
      statRef.current = null;
      cvRef.current = null;
      excessRef.current = null;
      safeRemoveSeries(chart, excessSeries);
      safeRemoveSeries(chart, cvSeries);
      safeRemoveSeries(chart, statSeries);
    };
  }, [chart]);

  useEffect(() => {
    if (!chart || !statRef.current || !cvRef.current || !excessRef.current) return;
    const sliced = sliceByCutoff(history, cutoff);
    statRef.current.setData(
      sliced.map((d) => ({ time: d.time as UTCTimestamp, value: d.stat }))
    );
    cvRef.current.setData(
      sliced.map((d) => ({ time: d.time as UTCTimestamp, value: d.cv }))
    );
    excessRef.current.setData(
      sliced.map((d) => ({
        time: d.time as UTCTimestamp,
        value: Number((d.stat - d.cv).toFixed(3)),
        color: d.stat > d.cv ? "#D55E00" : "#2A3140",
      }))
    );
    chart.timeScale().fitContent();
  }, [chart, history, cutoff]);

  return <div ref={containerRef} className="chart-container" />;
}
