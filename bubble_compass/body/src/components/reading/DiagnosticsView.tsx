import { useEffect, useMemo, useRef, useState } from "react";
import { buildCharts, type LayerBundle, type SleeveDef } from "../../diagnostics/chartSpecs";
import { diagLines, oddsPercent } from "../../diagnostics/diagReading";
import { rowBefore, rowOnOrBefore } from "../../narrator/heat";
import { readBook } from "../../narrator/scoreCopy";
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

function isoToUnix(iso: string): number {
  return Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / 1000;
}

function datesOf(layers: LayerBundle | undefined): string[] {
  const rows = layers?.dlinear ?? [];
  const unique = new Set(
    rows
      .map((r) => String(r.as_of ?? "").slice(0, 10))
      .filter((d) => d.length >= 10)
  );
  return [...unique].sort();
}

type PlotlyNs = {
  react: (el: HTMLElement, data: unknown[], layout: unknown, config?: unknown) => void;
  restyle: (el: HTMLElement, update: Record<string, unknown>, traces?: number[]) => void;
  relayout: (el: HTMLElement, update: Record<string, unknown>) => void;
};

type Trace = { x?: unknown; y?: unknown };

export function DiagnosticsView() {
  const currentAsset = useMarketStore((s) => s.currentAsset);
  const setCurrentAsset = useMarketStore((s) => s.setCurrentAsset);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  const setReplayTimestamp = useMarketStore((s) => s.setReplayTimestamp);

  const [byId, setById] = useState<Record<string, LayerBundle>>({});
  const [plotly, setPlotly] = useState<PlotlyNs | null>(null);
  const [liveText, setLiveText] = useState("");

  const heatRef = useRef<HTMLDivElement>(null);
  const rzRef = useRef<HTMLDivElement>(null);
  const stretchRef = useRef<HTMLDivElement>(null);
  const regimeRef = useRef<HTMLDivElement>(null);
  const drawn = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void import("plotly.js-dist-min").then((m) => {
      if (!cancelled) {
        setPlotly((m as { default?: PlotlyNs }).default ?? (m as unknown as PlotlyNs));
      }
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

  const spine = useMemo(() => {
    const fromStocks = datesOf(byId.SP500_TOTAL_RETURN);
    if (fromStocks.length) return fromStocks;
    let best: string[] = [];
    for (const layers of Object.values(byId)) {
      const dates = datesOf(layers);
      if (dates.length > best.length) best = dates;
    }
    return best;
  }, [byId]);

  const asOf = useMemo(() => {
    if (replayTimestamp != null) {
      return new Date(replayTimestamp * 1000).toISOString().slice(0, 10);
    }
    return spine[spine.length - 1] ?? "";
  }, [replayTimestamp, spine]);

  const sliderIndex = useMemo(() => {
    if (!spine.length) return 0;
    if (!asOf) return spine.length - 1;
    let best = 0;
    for (let i = 0; i < spine.length; i++) {
      if (spine[i]! <= asOf) best = i;
    }
    return best;
  }, [spine, asOf]);

  const xRange = useMemo((): [string, string] | undefined => {
    if (spine.length < 2) return undefined;
    return [spine[0]!, spine[spine.length - 1]!];
  }, [spine]);

  const charts = useMemo(() => {
    if (!Object.keys(byId).length || !asOf) return null;
    return buildCharts({
      layersByAsset: byId,
      selectedId: currentAsset,
      asOf,
      sleeves: SLEEVES,
      xRange,
    });
  }, [byId, currentAsset, asOf, xRange]);

  const book = BOOKS.find((b) => b.id === currentAsset) ?? {
    id: currentAsset,
    name: "This book",
  };
  const layers = byId[currentAsset];
  const lines = useMemo(() => {
    if (!layers || !asOf) return [];
    const now = readBook(book, layers, asOf);
    const prior = rowBefore(layers.dlinear, asOf);
    const prevDate = prior ? String(prior.as_of ?? "").slice(0, 10) : "";
    const prev = prevDate ? readBook(book, layers, prevDate) : null;
    const regime = rowOnOrBefore(layers.regime, asOf);
    const prevRegime = prevDate ? rowOnOrBefore(layers.regime, prevDate) : null;
    return diagLines({
      name: book.name,
      cash: book.cash,
      now,
      prev: prev ? { word: prev.word, heat: prev.heat } : null,
      nowDate: asOf,
      prevDate,
      boom: oddsPercent(regime?.boom_probability),
      bust: oddsPercent(regime?.bust_probability),
      prevBoom: oddsPercent(prevRegime?.boom_probability),
      prevBust: oddsPercent(prevRegime?.bust_probability),
    });
  }, [layers, asOf, book]);

  const paint = (mode: "react" | "restyle") => {
    if (!plotly || !charts) return;
    const cfg = { displayModeBar: false, responsive: true };
    const boxes: Array<[HTMLDivElement | null, { data: Trace[]; layout: Record<string, unknown> }]> = [
      [heatRef.current, charts.heat as { data: Trace[]; layout: Record<string, unknown> }],
      [rzRef.current, charts.residualZ as { data: Trace[]; layout: Record<string, unknown> }],
      [stretchRef.current, charts.stretch as { data: Trace[]; layout: Record<string, unknown> }],
      [regimeRef.current, charts.regime as { data: Trace[]; layout: Record<string, unknown> }],
    ];
    for (const [el, spec] of boxes) {
      if (!el) continue;
      const height = Math.max(el.clientHeight, 80);
      const width = Math.max(el.clientWidth, 80);
      const layout = { ...spec.layout, height, width };
      if (mode === "react" || !drawn.current) {
        plotly.react(el, spec.data, layout, cfg);
      } else {
        spec.data.forEach((tr, i) => {
          plotly.restyle(el, { x: [tr.x], y: [tr.y] }, [i]);
        });
        const update: Record<string, unknown> = { height, width };
        if (el !== heatRef.current) {
          update.shapes = spec.layout.shapes ?? [];
          if (xRange) update["xaxis.range"] = xRange;
        }
        plotly.relayout(el, update);
      }
    }
    drawn.current = true;
  };

  useEffect(() => {
    drawn.current = false;
    paint("react");
    // Book or loaded histories changed. The pin effect below moves the marker.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plotly, currentAsset, byId]);

  useEffect(() => {
    if (!drawn.current) {
      paint("react");
      return;
    }
    paint("restyle");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [charts]);

  useEffect(() => {
    if (!plotly) return;
    const nodes = [heatRef.current, rzRef.current, stretchRef.current, regimeRef.current];
    const ro = new ResizeObserver(() => {
      if (drawn.current) paint("restyle");
    });
    for (const n of nodes) if (n) ro.observe(n);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plotly, charts]);

  const linesRef = useRef(lines);
  linesRef.current = lines;

  const step = (dir: number) => {
    const next = Math.min(spine.length - 1, Math.max(0, sliderIndex + dir));
    const d = spine[next];
    if (!d) return;
    setReplayTimestamp(isoToUnix(d));
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.tagName === "SELECT" || target?.tagName === "TEXTAREA") return;
      if (target?.tagName === "INPUT" && target.id !== "diag-date") return;
      if (target?.id === "diag-date") return;
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      step(event.key === "ArrowRight" ? 1 : -1);
      setLiveText(linesRef.current.join(" "));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <article className="reading-page diagnostics-view">
      <div className="diag-controls">
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
        <label className="diag-date" htmlFor="diag-date">
          <span>{asOf ? plainDate(asOf) : "Loading"}</span>
          <input
            id="diag-date"
            type="range"
            min={0}
            max={Math.max(0, spine.length - 1)}
            value={sliderIndex}
            disabled={spine.length === 0}
            aria-valuetext={asOf ? plainDate(asOf) : "Loading"}
            onChange={(e) => {
              const d = spine[Number(e.target.value)];
              if (d) setReplayTimestamp(isoToUnix(d));
            }}
            onPointerUp={() => setLiveText(linesRef.current.join(" "))}
          />
        </label>
      </div>
      <div className="diag-board">
        <section className="diag-col">
          <h2>Heat</h2>
          <div ref={heatRef} className="diag-chart" />
        </section>
        <div className="diag-histories">
          <section className="diag-pane">
            <h2>Distance from the path</h2>
            <div ref={rzRef} className="diag-chart" />
          </section>
          <section className="diag-pane">
            <h2>Fast rise</h2>
            <div ref={stretchRef} className="diag-chart" />
          </section>
          <section className="diag-pane">
            <h2>Boom and bust</h2>
            <div ref={regimeRef} className="diag-chart" />
          </section>
        </div>
        <section className="diag-col diag-read">
          <h2>{book.name}</h2>
          {lines.length === 0 ? (
            <p>The series are still loading.</p>
          ) : (
            lines.map((line) => <p key={line}>{line}</p>)
          )}
          <p className="diag-live" aria-live="polite">
            {liveText}
          </p>
          <details className="diag-limits">
            <summary>Limits that do not change with the date</summary>
            <p>
              The oil book, the US inflation-linked book, and the Swiss franc
              book are total returns.
            </p>
            <p>
              The high-yield spread is one series shared across the books. Its
              unit changes around 1 Feb 2022, and after that the series is
              unchanged.
            </p>
            <p>Option and estimate feeds appear only as offline extracts.</p>
          </details>
        </section>
      </div>
    </article>
  );
}
