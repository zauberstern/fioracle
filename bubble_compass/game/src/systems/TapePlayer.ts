import universe from "../data/universe.json";
import historyFixture from "../data/history_fixture.json";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const HISTORY_BASE =
  import.meta.env.VITE_HISTORY_BASE ||
  `${import.meta.env.BASE_URL || "/"}../data/`;

function historyJsonUrl(asset: string): string {
  const base = HISTORY_BASE.endsWith("/") ? HISTORY_BASE : `${HISTORY_BASE}/`;
  return `${base}history/${encodeURIComponent(asset)}.json`;
}

export type LayerName =
  | "dlinear"
  | "bsadf"
  | "lppls"
  | "sentiment"
  | "regime"
  | "macro_debt";

export interface HistoryResponse {
  asset: string;
  layers: Partial<Record<LayerName, Array<Record<string, unknown>>>>;
}

export interface DeskHud {
  heat: number;
  stretch: number;
  crashWindow: string;
  sentiment: number;
  regime: string;
  spreadBps: number;
  ltv: number;
}

export interface TapeFrame {
  asOf: string;
  byAsset: Record<string, Record<LayerName, Record<string, unknown>>>;
}

function normDate(raw: unknown): string {
  const s = String(raw ?? "").slice(0, 10);
  return s;
}

function layerIndex(
  response: HistoryResponse
): Record<LayerName, Map<string, Record<string, unknown>>> {
  const out: Partial<Record<LayerName, Map<string, Record<string, unknown>>>> = {};
  for (const [layer, rows] of Object.entries(response.layers)) {
    const map = new Map<string, Record<string, unknown>>();
    for (const row of rows ?? []) {
      const d = normDate(row.as_of);
      if (d) map.set(d, row);
    }
    out[layer as LayerName] = map;
  }
  return out as Record<LayerName, Map<string, Record<string, unknown>>>;
}

export class TapePlayer {
  private frames: TapeFrame[] = [];
  private index = 0;
  private loaded = false;
  private source: "api" | "static" | "fixture" | "none" = "none";

  get hasTape(): boolean {
    return this.loaded && this.frames.length > 0;
  }

  get dataSource(): string {
    return this.source;
  }

  get currentIndex(): number {
    return this.index;
  }

  get timelineLength(): number {
    return this.frames.length;
  }

  currentAsOf(): string {
    return this.frames[this.index]?.asOf ?? "-";
  }

  currentFrame(): TapeFrame | null {
    return this.frames[this.index] ?? null;
  }

  async load(): Promise<boolean> {
    const assetIds = universe.sleeves.map((s) => s.id);
    const fromApi = await this.tryUrls(
      assetIds,
      (asset) => `${API_BASE}/api/v1/history/${asset}`
    );
    if (fromApi) {
      this.source = "api";
      this.loaded = true;
      return true;
    }
    const fromStatic = await this.tryUrls(assetIds, historyJsonUrl);
    if (fromStatic) {
      this.source = "static";
      this.loaded = true;
      return true;
    }
    const fromFixture = this.loadFixture();
    this.loaded = fromFixture;
    this.source = fromFixture ? "fixture" : "none";
    return fromFixture;
  }

  private async tryUrls(
    assetIds: string[],
    urlFor: (asset: string) => string
  ): Promise<boolean> {
    const responses: HistoryResponse[] = [];
    for (const asset of assetIds) {
      try {
        const res = await fetch(urlFor(asset));
        if (!res.ok) continue;
        const body = (await res.json()) as HistoryResponse;
        if (body.layers && Object.keys(body.layers).length > 0) {
          responses.push({ asset: body.asset ?? asset, layers: body.layers });
        }
      } catch {
        /* try next asset / source */
      }
    }
    if (responses.length === 0) return false;
    this.buildFrames(responses);
    return this.frames.length > 0;
  }

  private loadFixture(): boolean {
    const assets = historyFixture.assets as Record<string, HistoryResponse>;
    const responses = Object.values(assets);
    this.buildFrames(responses);
    return this.frames.length > 0;
  }

  private buildFrames(responses: HistoryResponse[]): void {
    const indexed = responses.map((r) => ({
      asset: r.asset,
      layers: layerIndex(r),
    }));
    const dateSet = new Set<string>();
    for (const { layers } of indexed) {
      for (const map of Object.values(layers)) {
        for (const d of map.keys()) dateSet.add(d);
      }
    }
    const dates = [...dateSet].sort();
    this.frames = dates.map((asOf) => {
      const byAsset: TapeFrame["byAsset"] = {};
      for (const { asset, layers } of indexed) {
        byAsset[asset] = {} as Record<LayerName, Record<string, unknown>>;
        for (const [layer, map] of Object.entries(layers) as [LayerName, Map<string, Record<string, unknown>>][]) {
          const row = map.get(asOf) ?? this.nearestBefore(map, asOf);
          if (row) byAsset[asset][layer] = row;
        }
      }
      return { asOf, byAsset };
    });
    this.index = 0;
  }

  private nearestBefore(
    map: Map<string, Record<string, unknown>>,
    asOf: string
  ): Record<string, unknown> | undefined {
    let best: string | null = null;
    for (const d of map.keys()) {
      if (d <= asOf && (best === null || d > best)) best = d;
    }
    return best ? map.get(best) : undefined;
  }

  jumpToDate(isoDate: string): boolean {
    const target = isoDate.slice(0, 10);
    const idx = this.frames.findIndex((f) => f.asOf >= target);
    if (idx < 0) return false;
    this.index = idx;
    return true;
  }

  advance(): boolean {
    if (this.index >= this.frames.length - 1) return false;
    this.index += 1;
    return true;
  }

  rewindToStart(): void {
    this.index = 0;
  }

  benchmarkHud(): DeskHud {
    const bench = universe.benchmark;
    const frame = this.currentFrame();
    const empty: DeskHud = {
      heat: 0,
      stretch: 0,
      crashWindow: "-",
      sentiment: Number.NaN,
      regime: "unknown",
      spreadBps: 0,
      ltv: 0.5,
    };
    if (!frame) return empty;
    const layers = frame.byAsset[bench];
    if (!layers) return empty;
    const d = layers.dlinear ?? {};
    const b = layers.bsadf ?? {};
    const l = layers.lppls ?? {};
    const s = layers.sentiment ?? {};
    const r = layers.regime ?? {};
    const m = layers.macro_debt ?? {};
    const crashStart = l.crash_window_start ?? l.crashWindowStart;
    const crashEnd = l.crash_window_end ?? l.crashWindowEnd;
    const crashWindow =
      crashStart && crashEnd
        ? `${String(crashStart).slice(0, 10)}..${String(crashEnd).slice(0, 10)}`
        : "-";
    const residualZ = Number(d.residual_z ?? d.residualZ ?? 0);
    const bsadfStat = Number(b.bsadf_stat ?? b.bsadfStat ?? 0);
    const cv = Number(b.critical_value ?? b.criticalValue ?? 1.49);
    const bubbleFlag = Boolean(b.bubble_flag ?? b.bubbleFlag ?? false);
    const lpp = Number(l.lpp_confidence ?? l.lppConfidence ?? 0);
    const sentUnavailable = Boolean(s.unavailable ?? true);
    const sentVel = Number(s.sentiment_velocity ?? s.sentimentVelocity ?? 0);
    const residualBoost = Math.min(40, Math.abs(residualZ) * 12);
    const bsadfBoost = bubbleFlag
      ? 25 + Math.max(0, bsadfStat - cv) * 8
      : Math.max(0, bsadfStat) * 5;
    const heat = Math.max(
      0,
      Math.min(100, residualBoost + bsadfBoost + lpp * 30 + (sentUnavailable ? 0 : Math.abs(sentVel) * 15))
    );
    return {
      heat,
      stretch: bsadfStat,
      crashWindow,
      sentiment: sentUnavailable ? Number.NaN : sentVel,
      regime: String(r.regime_state ?? r.regimeState ?? "unknown"),
      spreadBps: Number(m.gap ?? m.spread_bps ?? m.spreadBps ?? 0),
      ltv: Number(m.ltv ?? 0.5),
    };
  }

  sleeveDailyReturn(sleeveId: string): number {
    // History parquet has no daily_return; derive from DLinear trend path.
    if (this.index <= 0) return 0;
    const cur = this.frames[this.index]?.byAsset[sleeveId]?.dlinear;
    const prev = this.frames[this.index - 1]?.byAsset[sleeveId]?.dlinear;
    if (!cur || !prev) return 0;
    const t0 = Number(prev.trend ?? 0);
    const t1 = Number(cur.trend ?? 0);
    if (!Number.isFinite(t0) || !Number.isFinite(t1) || t0 === 0) return 0;
    return (t1 - t0) / Math.abs(t0);
  }
}
