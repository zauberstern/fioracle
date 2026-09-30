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
import { sliceByCutoff, useChartCutoff } from "../../hooks/useChartData";
import { useMarketStore } from "../../store/marketStore";

export function LPPLSChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chart = useLightweightChart(containerRef);
  const priceRef = useRef<ISeriesApi<"Line"> | null>(null);
  const fittedRef = useRef<ISeriesApi<"Line"> | null>(null);
  const history = useMarketStore((s) => s.lpplsHistory);
  const cutoff = useChartCutoff();
  const asset = useMarketStore((s) => s.currentAsset);
  const lppls = useMarketStore((s) => s.getAssetState(asset).lppls);

  useEffect(() => {
    if (!chart) return;

    const priceSeries = chart.addSeries(LineSeries, {
      color: "#9AA4B2",
      lineWidth: 1,
      title: "Price",
    });
    const fittedSeries = chart.addSeries(LineSeries, {
      color: "#D55E00",
      lineWidth: 2,
      title: "Fit",
    });
    priceRef.current = priceSeries;
    fittedRef.current = fittedSeries;

    return () => {
      priceRef.current = null;
      fittedRef.current = null;
      safeRemoveSeries(chart, fittedSeries);
      safeRemoveSeries(chart, priceSeries);
    };
  }, [chart]);

  useEffect(() => {
    if (!chart || !priceRef.current || !fittedRef.current) return;
    const sliced = sliceByCutoff(history, cutoff);
    priceRef.current.setData(
      sliced.map((d) => ({ time: d.time as UTCTimestamp, value: d.price }))
    );
    fittedRef.current.setData(
      sliced.map((d) => ({ time: d.time as UTCTimestamp, value: d.fitted }))
    );

    if (lppls.crashWindowStart) {
      const t = Math.floor(lppls.crashWindowStart.getTime() / 1000);
      fittedRef.current.createPriceLine({
        price: sliced[sliced.length - 1]?.fitted ?? 0,
        color: "#E69F00",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `window ${new Date(t * 1000).toISOString().slice(0, 10)}`,
      });
    }

    chart.timeScale().fitContent();
  }, [chart, history, cutoff, lppls]);

  return <div ref={containerRef} className="chart-container" />;
}
