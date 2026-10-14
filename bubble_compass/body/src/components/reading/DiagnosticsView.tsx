import { useEffect, useMemo, useRef, useState } from "react";
import { buildCharts, REGIME_FLAT_NOTE, type LayerBundle, type SleeveDef } from "../../diagnostics/chartSpecs";
import { useMarketStore } from "../../store/marketStore";
import { BOOKS } from "../../../../shared/books";
import { READING } from "../../../../shared/palette";
import { plainDate } from "../../../../shared/plainDate";


const HISTORY_BASE =
  import.meta.env.VITE_HISTORY_BASE ||
  `${import.meta.env.BASE_URL || "/"}data/`;

const SLEEVES: SleeveDef[] = BOOKS.map((b, i) => ({
  id: b.id,
  label: b.name,
  color: i % 2 === 0 ? READING.ink : READING.signal,
  cash: b.cash,
}));

function historyUrl(asset: string): string {
  const base = HISTORY_BASE.endsWith("/") ? HISTORY_BASE : `${HISTORY_BASE}/`;
  return `${base}history/${encodeURIComponent(asset)}.json`;
}

async function fetchLayers(asset: string): Promise<LayerBundle | null> {
  try {
    const res = await fetch(historyUrl(asset));
    if (!res.ok) return null;
    const body = await res.json();
    return (body.layers ?? body) as LayerBundle;
  } catch {
    return null;
  }
}

type PlotlyNs = {
  react: (
    el: HTMLElement,
    data: unknown[],
    layout: unknown,
    config?: unknown
  ) => void;
};

export function DiagnosticsView() {
  const rawLayers = useMarketStore((s) => s.rawLayers);
  const currentAsset = useMarketStore((s) => s.currentAsset);
  const setCurrentAsset = useMarketStore((s) => s.setCurrentAsset);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);

  const [byId, setById] = useState<Record<string, LayerBundle>>({});
  const [plotly, setPlotly] = useState<PlotlyNs | null>(null);

  const heatRef = useRef<HTMLDivElement>(null);
  const rzRef = useRef<HTMLDivElement>(null);
  const stretchRef = useRef<HTMLDivElement>(null);
  const regimeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void import("plotly.js-dist-min").then((m) => {
      if (!cancelled) setPlotly((m as { default?: PlotlyNs }).default ?? (m as unknown as PlotlyNs));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const out: Record<string, LayerBundle> = {};
      await Promise.all(
        SLEEVES.map(async (s) => {
          const layers = await fetchLayers(s.id);
          if (layers) out[s.id] = layers;
        })
      );
      if (!cancelled) setById(out);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const dates = useMemo(() => {
    const rows = (byId[currentAsset] ?? rawLayers).dlinear ?? [];
    const unique = new Set(
      rows
        .map((r) => String(r.as_of ?? "").slice(0, 10))
        .filter((d) => d.length >= 10)
    );
    return [...unique].sort();
  }, [byId, currentAsset, rawLayers]);

  const asOf = useMemo(() => {
    if (replayTimestamp != null) {
      return new Date(replayTimestamp * 1000).toISOString().slice(0, 10);
    }
    return dates[dates.length - 1] ?? "2008-01-01";
  }, [replayTimestamp, dates]);

  const charts = useMemo(() => {
    if (!Object.keys(byId).length) return null;
    return buildCharts({
      layersByAsset: byId,
      selectedId: currentAsset,
      asOf,
      sleeves: SLEEVES,
    });
  }, [byId, currentAsset, asOf]);

  useEffect(() => {
    if (!plotly || !charts) return;
    const cfg = { displayModeBar: false, responsive: true };
    if (heatRef.current) {
      plotly.react(heatRef.current, charts.heat.data, charts.heat.layout, cfg);
    }
    if (rzRef.current) {
      plotly.react(
        rzRef.current,
        charts.residualZ.data,
        charts.residualZ.layout,
        cfg
      );
    }
    if (stretchRef.current) {
      plotly.react(
        stretchRef.current,
        charts.stretch.data,
        charts.stretch.layout,
        cfg
      );
    }
    if (regimeRef.current) {
      plotly.react(
        regimeRef.current,
        charts.regime.data,
        charts.regime.layout,
        cfg
      );
    }
  }, [plotly, charts]);

  return (
    <article className="reading-page diagnostics-view">
      <h1>Diagnostics</h1>
      <p className="reading-lede">
        One row per book for the selected date. Price levels are not included.
      </p>

      <p className="diag-caption">
        {dates.length === 0
          ? "The series are still loading."
          : plainDate(asOf)}
      </p>

      <label htmlFor="diag-sleeve">
        Book{" "}
        <select
          id="diag-sleeve"
          value={currentAsset}
          onChange={(e) => setCurrentAsset(e.target.value)}
        >
          {SLEEVES.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </label>

      <div ref={heatRef} className="diag-chart" />
      <div ref={rzRef} className="diag-chart" />
      <div ref={stretchRef} className="diag-chart" />
      {charts?.cashStretchNote ? (
        <p className="diag-note">
          Cash is marked stretched throughout this history. The weekly summary
          does not treat cash as a bubble.
        </p>
      ) : null}
      <div ref={regimeRef} className="diag-chart" />
      {charts?.regimeWordFlat ? (
        <p className="diag-note">{REGIME_FLAT_NOTE}</p>
      ) : null}
      {charts?.prophecy === "empty" ? (
        <p className="diag-note">Crash-timing estimates are not available.</p>
      ) : null}

      <p className="diag-caption">
        The books are the series on this page. Foreign exchange levels are not
        included, apart from the Swiss franc total return.
      </p>
      <p className="diag-caption">
        The high-yield spread is a single series shared across the books. Its
        unit changes around 1 Feb 2022, after which the series is unchanged.
        Headline sentiment and company credit are not in this history. Option
        and estimate feeds appear only as offline extracts.
      </p>

    </article>
  );
}
