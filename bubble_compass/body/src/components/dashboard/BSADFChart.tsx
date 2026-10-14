import { useEffect, useMemo, useRef } from "react";
import {
  LineSeries,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  useLightweightChart,
  safeRemoveSeries,
} from "../../hooks/useLightweightChart";
import {
  FAST_RISE_PLOT_TOP,
  chartRows,
  plotFastRise,
  useChartCutoff,
} from "../../hooks/useChartData";
import { useMarketStore } from "../../store/marketStore";
import { plainDate } from "../../../../shared/plainDate";

export function BSADFChart({ fullSpan = false }: { fullSpan?: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chart = useLightweightChart(containerRef);
  const statRef = useRef<ISeriesApi<"Line"> | null>(null);
  const cvRef = useRef<ISeriesApi<"Line"> | null>(null);
  const history = useMarketStore((s) => s.bsadfHistory);
  const cutoff = useChartCutoff();

  useEffect(() => {
    if (!chart) return;

    const statSeries = chart.addSeries(LineSeries, {
      color: "#0072B2",
      lineWidth: 2,
      title: "Fast rise",
    });
    const cvSeries = chart.addSeries(LineSeries, {
      color: "#5C5E62",
      lineWidth: 1,
      lineStyle: 2,
      title: "Ordinary line",
    });

    statRef.current = statSeries;
    cvRef.current = cvSeries;

    return () => {
      statRef.current = null;
      cvRef.current = null;
      safeRemoveSeries(chart, cvSeries);
      safeRemoveSeries(chart, statSeries);
    };
  }, [chart]);

  const shown = useMemo(
    () => chartRows(history, cutoff, fullSpan),
    [history, cutoff, fullSpan]
  );
  const clipped = shown.filter((d) => d.stat > FAST_RISE_PLOT_TOP).length;
  const tip = shown[shown.length - 1];

  useEffect(() => {
    if (!chart || !statRef.current || !cvRef.current) return;
    statRef.current.setData(
      shown.map((d) => ({
        time: d.time as UTCTimestamp,
        value: plotFastRise(d.stat),
      }))
    );
    cvRef.current.setData(
      shown.map((d) => ({ time: d.time as UTCTimestamp, value: d.cv }))
    );
    chart.timeScale().fitContent();
  }, [chart, shown]);

  const tipDate =
    tip != null
      ? plainDate(new Date(tip.time * 1000).toISOString().slice(0, 10))
      : "";
  const tipReading =
    tip == null
      ? ""
      : Math.abs(tip.stat) >= 100
        ? Math.round(tip.stat).toLocaleString("en-US")
        : tip.stat.toFixed(2);
  const first = shown[0];
  const span =
    fullSpan && first && tip
      ? `This chart runs from ${plainDate(new Date(first.time * 1000).toISOString().slice(0, 10))} through ${tipDate}. `
      : "";
  const caption = !tip
    ? "The series are still loading."
    : clipped > 0
      ? `${span}On ${tipDate} the fast-rise reading is ${tipReading}. The ordinary line is ${tip.cv.toFixed(2)}. ${clipped} ${clipped === 1 ? "row sits" : "rows sit"} far above that line, so those points are drawn at ${FAST_RISE_PLOT_TOP}.`
      : `${span}On ${tipDate} the fast-rise reading is ${tipReading}. The ordinary line is ${tip.cv.toFixed(2)}.`;

  return (
    <div className="score-chart-wrap">
      <p className="chart-caption">{caption}</p>
      <div ref={containerRef} className="chart-container" />
    </div>
  );
}
