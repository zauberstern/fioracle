import { useEffect, useRef } from "react";
import {
  LineSeries,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  useLightweightChart,
  safeRemoveSeries,
} from "../../hooks/useLightweightChart";
import { chartRows, useChartCutoff } from "../../hooks/useChartData";
import { useMarketStore } from "../../store/marketStore";

export function LPPLSChart({ fullSpan = false }: { fullSpan?: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chart = useLightweightChart(containerRef);
  const confRef = useRef<ISeriesApi<"Line"> | null>(null);
  const history = useMarketStore((s) => s.lpplsHistory);
  const cutoff = useChartCutoff();
  const asset = useMarketStore((s) => s.currentAsset);
  const lppls = useMarketStore((s) => s.getAssetState(asset).lppls);

  useEffect(() => {
    if (!chart) return;

    const confSeries = chart.addSeries(LineSeries, {
      color: "#0072B2",
      lineWidth: 2,
      title: "Break date",
    });
    confRef.current = confSeries;

    return () => {
      confRef.current = null;
      safeRemoveSeries(chart, confSeries);
    };
  }, [chart]);

  useEffect(() => {
    if (!chart || !confRef.current) return;
    if (lppls.unavailable || history.length === 0) {
      confRef.current.setData([]);
      return;
    }
    const sliced = chartRows(history, cutoff, fullSpan);
    confRef.current.setData(
      sliced.map((d) => ({
        time: d.time as UTCTimestamp,
        value: d.confidence,
      }))
    );

    const tip = sliced[sliced.length - 1];
    if (tip?.tcEstimate != null) {
      confRef.current.createPriceLine({
        price: tip.confidence,
        color: "#5C5E62",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `tc ${new Date(tip.tcEstimate * 1000).toISOString().slice(0, 10)}`,
      });
    } else if (lppls.crashWindowStart) {
      const t = Math.floor(lppls.crashWindowStart.getTime() / 1000);
      confRef.current.createPriceLine({
        price: tip?.confidence ?? 0,
        color: "#5C5E62",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `window ${new Date(t * 1000).toISOString().slice(0, 10)}`,
      });
    }

    chart.timeScale().fitContent();
  }, [chart, history, cutoff, fullSpan, lppls]);

  if (lppls.unavailable) {
    return (
      <div className="chart-container chart-empty" role="status">
        A date for a break is not in this history, so this chart has no line.
      </div>
    );
  }

  return <div ref={containerRef} className="chart-container" />;
}
