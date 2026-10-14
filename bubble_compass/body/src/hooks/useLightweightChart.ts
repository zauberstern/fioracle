import { useEffect, useState, type RefObject } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type SeriesType,
} from "lightweight-charts";

/**
 * Owns one Lightweight Charts instance for a container.
 * Returns null until mounted. Callers must not removeSeries after unmount;
 * disposing the chart clears series. Prefer setData on a stable series.
 */
export function useLightweightChart(
  containerRef: RefObject<HTMLDivElement | null>
): IChartApi | null {
  const [chart, setChart] = useState<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const instance = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "#FFFEFB" },
        textColor: "#171A20",
        fontFamily: "IBM Plex Sans, sans-serif",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "#E4E2DC" },
        horzLines: { color: "#E4E2DC" },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      rightPriceScale: { borderColor: "#D0D1D2" },
      timeScale: {
        borderColor: "#D0D1D2",
        timeVisible: true,
        secondsVisible: false,
      },
      width: Math.max(el.clientWidth, 1),
      height: Math.max(el.clientHeight, 180),
    });

    setChart(instance);

    const handleResize = () => {
      if (!containerRef.current) return;
      instance.applyOptions({
        width: Math.max(containerRef.current.clientWidth, 1),
        height: Math.max(containerRef.current.clientHeight, 180),
      });
    };

    const ro = new ResizeObserver(handleResize);
    ro.observe(el);
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      ro.disconnect();
      setChart(null);
      // chart.remove() disposes every series; do not removeSeries afterward
      instance.remove();
    };
  }, [containerRef]);

  return chart;
}

/** Safe series teardown when the chart may already be disposed. */
export function safeRemoveSeries(
  chart: IChartApi | null | undefined,
  series: ISeriesApi<SeriesType> | null | undefined
): void {
  if (!chart || !series) return;
  try {
    chart.removeSeries(series);
  } catch (err) {
    console.debug(
      "[charts] removeSeries skipped (chart already disposed)",
      err instanceof Error ? err.message : err
    );
  }
}
