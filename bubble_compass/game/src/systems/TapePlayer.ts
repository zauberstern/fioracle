import universe from "../data/universe.json";
import { snapFrameIndex } from "../../../shared/snapAsOf";
import { evaluateCrashGate } from "../../../shared/crashGate";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const HISTORY_BASE =
  import.meta.env.VITE_HISTORY_BASE ||
  (import.meta.env.DEV
    ? "http://localhost:5173/data/"
    : `${import.meta.env.BASE_URL || "/"}../data/`);

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
  | "macro_debt"
  | "credit_trajectory";

export type TapeSource = "api" | "static" | "empty";

export interface HistoryResponse {
  asset: string;
  layers: Partial<Record<LayerName, Array<Record<string, unknown>>>>;
}

export interface DeskHud {
  heat: number;
  stretch: number;
  criticalValue: number;
  bubbleFlag: boolean;
  crashWindow: string;
  sentiment: number;
  regime: string;
  spreadBps: number;
  ltv: number;
  oasHistory: number[];
}

export interface TapeFrame {
  asOf: string;
  byAsset: Record<string, Partial<Record<LayerName, Record<string, unknown>>>>;
}

function normDate(raw: unknown): string {
  return String(raw ?? "").slice(0, 10);
}

/**
 * Read tape daily_return from a dlinear tip row.
 * Missing / null / non-finite stays NaN (no print), not a scored 0.
 */
export function dailyReturnFromRow(
  cur: Record<string, unknown> | undefined | null
): number {
  if (!cur) return Number.NaN;
  if (cur.daily_return == null && cur.dailyReturn == null) return Number.NaN;
  const fromTape = Number(cur.daily_return ?? cur.dailyReturn);
  return Number.isFinite(fromTape) ? fromTape : Number.NaN;
}

/** Rift window only when LPPLS is present and not unavailable. */
export function lpplsCrashWindow(l: Record<string, unknown>): string {
  if (!l || Object.keys(l).length === 0) return "-";
  if (l.unavailable === true) return "-";
  const crashStart = l.crash_window_start ?? l.crashWindowStart;
  const crashEnd = l.crash_window_end ?? l.crashWindowEnd;
  if (!crashStart || !crashEnd) return "-";
  return `${String(crashStart).slice(0, 10)}..${String(crashEnd).slice(0, 10)}`;
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
  private source: TapeSource = "empty";
  private loadError = "";

  get hasTape(): boolean {
    return this.loaded && this.frames.length > 0 && this.source !== "empty";
  }

  get dataSource(): TapeSource {
    return this.source;
  }

  get errorMessage(): string {
    return this.loadError;
  }

  get currentIndex(): number {
    return this.index;
  }

  get timelineLength(): number {
    return this.frames.length;
  }

  asOfDates(): string[] {
    return this.frames.map((f) => f.asOf);
  }

  currentAsOf(): string {
    return this.frames[this.index]?.asOf ?? "-";
  }

  /** Next tip after advance, or null at tape end. */
  peekNextAsOf(): string | null {
    if (this.index >= this.frames.length - 1) return null;
    return this.frames[this.index + 1]?.asOf ?? null;
  }

  currentFrame(): TapeFrame | null {
    return this.frames[this.index] ?? null;
  }

  async load(): Promise<boolean> {
    const assetIds = universe.sleeves.map((s) => s.id);
    const fromApi = await this.tryUrlsComplete(
      assetIds,
      (asset) => `${API_BASE}/api/v1/history/${asset}`
    );
    if (fromApi) {
      this.source = "api";
      this.loaded = true;
      this.loadError = "";
      return true;
    }
    const fromStatic = await this.tryUrlsComplete(assetIds, historyJsonUrl);
    if (fromStatic) {
      this.source = "static";
      this.loaded = true;
      this.loadError = "";
      return true;
    }
    this.source = "empty";
    this.loaded = false;
    this.frames = [];
    this.loadError = "No history yet. Export the compass pages or start the API.";
    return false;
  }

  /** Require every sleeve to succeed - never silent partial / fixture mix. */
  private async tryUrlsComplete(
    assetIds: string[],
    urlFor: (asset: string) => string
  ): Promise<boolean> {
    const responses: HistoryResponse[] = [];
    for (const asset of assetIds) {
      try {
        const res = await fetch(urlFor(asset));
        if (!res.ok) {
          this.loadError = `Missing history for ${asset} (${res.status})`;
          return false;
        }
        const body = (await res.json()) as HistoryResponse;
        if (!body.layers || Object.keys(body.layers).length === 0) {
          this.loadError = `Empty layers for ${asset}`;
          return false;
        }
        responses.push({ asset: body.asset ?? asset, layers: body.layers });
      } catch (err) {
        this.loadError = `Fetch failed for ${asset}: ${String(err)}`;
        return false;
      }
    }
    if (responses.length !== assetIds.length) return false;
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
        byAsset[asset] = {};
        for (const [layer, map] of Object.entries(layers) as [
          LayerName,
          Map<string, Record<string, unknown>>,
        ][]) {
          const row = map.get(asOf) ?? this.nearestBefore(map, asOf);
          if (row) byAsset[asset]![layer] = row;
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
    const idx = snapFrameIndex(this.asOfDates(), isoDate);
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

  oasHistory(limit = 8): number[] {
    const bench = universe.benchmark;
    const out: number[] = [];
    const start = Math.max(0, this.index - limit + 1);
    for (let i = start; i <= this.index; i++) {
      const credit = this.frames[i]?.byAsset[bench]?.credit_trajectory;
      const oas = Number(credit?.hy_oas_level_bps ?? credit?.hy_oas_level);
      if (Number.isFinite(oas)) out.push(oas);
    }
    return out;
  }

  benchmarkHud(): DeskHud {
    const bench = universe.benchmark;
    const frame = this.currentFrame();
    const empty: DeskHud = {
      heat: 0,
      stretch: 0,
      criticalValue: 1.49,
      bubbleFlag: false,
      crashWindow: "-",
      sentiment: Number.NaN,
      regime: "unknown",
      spreadBps: Number.NaN,
      ltv: Number.NaN,
      oasHistory: [],
    };
    if (!frame) return empty;
    const layers = frame.byAsset[bench];
    if (!layers) return empty;
    const d = layers.dlinear ?? {};
    const b = layers.bsadf ?? {};
    const l = layers.lppls ?? {};
    const s = layers.sentiment ?? {};
    const r = layers.regime ?? {};
    const credit = layers.credit_trajectory ?? {};
    const lpplsUnavailable =
      !l || Object.keys(l).length === 0 || l.unavailable === true;
    const crashWindow = lpplsUnavailable ? "-" : lpplsCrashWindow(l);
    const lpp = lpplsUnavailable
      ? 0
      : Number(l.lpp_confidence ?? l.lppConfidence ?? 0);
    const sentUnavailable =
      s.unavailable === true ||
      s.sentiment_velocity == null ||
      s.sentimentVelocity == null;
    const sentVel = Number(s.sentiment_velocity ?? s.sentimentVelocity ?? 0);
    const residualZ = Number(d.residual_z ?? d.residualZ ?? 0);
    const bsadfStat = Number(b.bsadf_stat ?? b.bsadfStat ?? 0);
    const cv = Number(b.critical_value ?? b.criticalValue ?? 1.49);
    const bubbleFlag = Boolean(b.bubble_flag ?? b.bubbleFlag ?? false);
    const residualBoost = Math.min(40, Math.max(0, residualZ) * 12);
    const bsadfBoost = bubbleFlag
      ? 25 + Math.max(0, bsadfStat - cv) * 8
      : Math.max(0, bsadfStat) * 5;
    const heat = Math.max(
      0,
      Math.min(
        100,
        residualBoost +
          bsadfBoost +
          lpp * 30 +
          (sentUnavailable ? 0 : Math.abs(sentVel) * 15)
      )
    );
    const oas = Number(credit.hy_oas_level_bps ?? credit.hy_oas_level ?? Number.NaN);
    return {
      heat,
      stretch: bsadfStat,
      criticalValue: cv,
      bubbleFlag,
      crashWindow,
      sentiment: sentUnavailable ? Number.NaN : sentVel,
      regime: String(r.regime_state ?? r.regimeState ?? "unknown"),
      spreadBps: Number.isFinite(oas) ? oas : Number.NaN,
      ltv: Number.NaN,
      oasHistory: this.oasHistory(8),
    };
  }

  sleeveDailyReturn(sleeveId: string): number {
    const cur = this.frames[this.index]?.byAsset[sleeveId]?.dlinear;
    return dailyReturnFromRow(cur);
  }

  shouldCrash(portfolioReturn: number): { triggered: boolean; reason: string } {
    const hud = this.benchmarkHud();
    return evaluateCrashGate({
      heat: hud.heat,
      bubbleFlag: hud.bubbleFlag,
      stretch: hud.stretch,
      criticalValue: hud.criticalValue,
      portfolioReturn,
    });
  }
}
