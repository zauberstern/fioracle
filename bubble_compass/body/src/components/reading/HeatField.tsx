import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

export type HeatCol = {
  id: string;
  name: string;
  values: number[];
};

type Props = {
  dates: string[];
  cols: HeatCol[];
  index: number;
  activeId: string | null;
};

const QUIET = "rgba(23, 26, 32, 0.28)";
const FOCUS = "#0072B2";

function unix(iso: string): number {
  return Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / 1000;
}

function placeCursor(u: uPlot, iso: string) {
  const left = u.valToPos(unix(iso), "x");
  if (!Number.isFinite(left)) return;
  u.setCursor({ left, top: 0 });
}

/** uPlot commits scales in a microtask, so the cursor has to wait for that. */
function placeSoon(u: uPlot, isoAt: () => string | undefined) {
  queueMicrotask(() => {
    const iso = isoAt();
    if (iso) placeCursor(u, iso);
  });
}

/** 23 heat lines. The cursor follows the date slider. Hover in the matrix thickens one line. */
export function HeatField({ dates, cols, index, activeId }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const indexRef = useRef(index);
  const datesRef = useRef(dates);
  indexRef.current = index;
  datesRef.current = dates;

  useEffect(() => {
    const el = host.current;
    if (!el || dates.length < 2 || cols.length === 0) return;
    const times = dates.map(unix);
    const data: uPlot.AlignedData = [times, ...cols.map((c) => c.values)];
    const u = new uPlot(
      {
        width: Math.max(el.clientWidth, 320),
        height: 280,
        scales: {
          y: { range: () => [0, 100] },
        },
        axes: [
          {
            stroke: () => "#5C5E62",
            grid: { stroke: () => "#E4E2DC" },
            ticks: { stroke: () => "#D0D1D2" },
          },
          {
            stroke: () => "#5C5E62",
            grid: { stroke: () => "#E4E2DC" },
            ticks: { stroke: () => "#D0D1D2" },
          },
        ],
        legend: { show: false },
        cursor: {
          x: true,
          y: false,
          points: { show: false },
          drag: { x: false, y: false },
          bind: {
            mousemove: () => () => null,
            mouseleave: () => () => null,
          },
        },
        series: [
          {},
          ...cols.map((c) => ({
            label: c.name,
            stroke: () => QUIET,
            width: 1,
          })),
        ],
        hooks: {
          draw: [
            (chart) => {
              const iso = datesRef.current[indexRef.current];
              if (!iso) return;
              placeCursor(chart, iso);
            },
          ],
        },
      },
      data,
      el
    );
    plot.current = u;
    const xMin = times[0];
    const xMax = times[times.length - 1];
    if (xMin != null && xMax != null && xMax > xMin) {
      u.setScale("x", { min: xMin, max: xMax });
    }
    const isoAt = () => datesRef.current[indexRef.current];
    placeSoon(u, isoAt);
    const ro = new ResizeObserver(() => {
      if (!host.current) return;
      u.setSize({ width: Math.max(host.current.clientWidth, 320), height: 280 });
      placeSoon(u, isoAt);
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      u.destroy();
      plot.current = null;
    };
  }, [dates, cols]);

  useEffect(() => {
    const u = plot.current;
    const iso = dates[index];
    if (!u || !iso) return;
    placeCursor(u, iso);
  }, [index, dates, cols]);

  useEffect(() => {
    const u = plot.current;
    if (!u) return;
    // redraw() before the first scale commit would publish a null x range.
    queueMicrotask(() => {
      if (plot.current !== u) return;
      cols.forEach((c, i) => {
        const series = u.series[i + 1];
        if (!series) return;
        const on = c.id === activeId;
        series.stroke = () => (on ? FOCUS : QUIET);
        series.width = on ? 2 : 1;
      });
      u.redraw(true);
    });
  }, [activeId, cols]);

  return <div ref={host} className="heat-field" />;
}
