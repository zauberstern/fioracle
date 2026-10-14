import { create } from "zustand";
import gsap from "gsap";
import {
  snapAsOfIso as sharedSnapAsOfIso,
  rowDateKey,
  type LayerRows,
} from "../../../shared/snapAsOf";

/** Re-export shared SoT (latest as_of <= pin). */
export function snapAsOfIso(layers: LayerRows, dateIso: string): string | null {
  return sharedSnapAsOfIso(layers, dateIso);
}

export interface DLinearState {
  trend: number;
  residual: number;
  residualZ: number;
}

export interface BSADFState {
  bsadfStat: number;
  criticalValue: number;
  bubbleFlag: boolean;
}

export interface LPPLSState {
  lppConfidence: number;
  crashWindowStart: Date | null;
  crashWindowEnd: Date | null;
  unavailable?: boolean;
  tcEstimate?: Date | null;
}

export interface SentimentState {
  sentimentVelocity: number;
  sentimentLevel: number;
  unavailable?: boolean;
}

export interface RegimeState {
  regimeState: "normal" | "boom" | "bust";
  regimeConfidence: number;
  boomProbability: number;
  bustProbability: number;
}

export interface AssetState {
  dlinear: DLinearState;
  bsadf: BSADFState;
  lppls: LPPLSState;
  sentiment: SentimentState;
  regime: RegimeState;
}

export interface TimeValuePoint {
  time: number;
  value: number;
}

export interface BSADFPoint {
  time: number;
  stat: number;
  cv: number;
}

export interface LPPLSPoint {
  time: number;
  confidence: number;
  tcEstimate: number | null;
}

const defaultAssetState: AssetState = {
  dlinear: { trend: 100, residual: 0, residualZ: 0 },
  bsadf: { bsadfStat: 0, criticalValue: 2.0, bubbleFlag: false },
  lppls: {
    lppConfidence: 0,
    crashWindowStart: null,
    crashWindowEnd: null,
    unavailable: true,
    tcEstimate: null,
  },
  sentiment: { sentimentVelocity: 0, sentimentLevel: 0, unavailable: true },
  regime: {
    regimeState: "normal",
    regimeConfidence: 0.8,
    boomProbability: 0.1,
    bustProbability: 0.1,
  },
};

interface Interpolated {
  terrainHeight: number;
  terrainBumpiness: number;
  obeliskGlow: number;
  riftIntensity: number;
  shimmerStrength: number;
  crowdMomentum: number;
}

/**
 * Offline fixture only. Callers must refuse when API/static tape exists.
 * Kept for unit tests; product path uses empty-state when no tape.
 */
export function seedHistories(days = 180) {
  const now = Math.floor(Date.now() / 1000);
  const day = 86400;
  const scoreHistory: TimeValuePoint[] = [];
  const bsadfHistory: BSADFPoint[] = [];
  const lpplsHistory: LPPLSPoint[] = [];
  const sentimentHistory: TimeValuePoint[] = [];

  let score = 28;
  for (let i = days; i >= 0; i--) {
    const time = now - i * day;
    const wave = Math.sin((days - i) / 18) * 12;
    const ramp = Math.max(0, (days - i - 90) / 4);
    score = Math.max(5, Math.min(95, 28 + wave + ramp));
    const cv = 2.0;
    const stat = 1.2 + score / 40;

    scoreHistory.push({ time, value: Number(score.toFixed(1)) });
    bsadfHistory.push({ time, stat: Number(stat.toFixed(3)), cv });
    lpplsHistory.push({
      time,
      confidence: Number((score / 100).toFixed(3)),
      tcEstimate: null,
    });
  }

  return { scoreHistory, bsadfHistory, lpplsHistory, sentimentHistory };
}

function bubbleScoreFromState(state: AssetState): number {
  // Signed residual stretch: positive residual_z adds heat; |z| alone is not overheat.
  const residualBoost = Math.min(40, Math.max(0, state.dlinear.residualZ) * 12);
  const bsadfBoost = state.bsadf.bubbleFlag
    ? 25 + Math.max(0, state.bsadf.bsadfStat - state.bsadf.criticalValue) * 8
    : Math.max(0, state.bsadf.bsadfStat) * 5;
  const lpplsBoost = state.lppls.unavailable
    ? 0
    : (Number.isFinite(state.lppls.lppConfidence) ? state.lppls.lppConfidence : 0) * 30;
  const sentimentBoost = state.sentiment.unavailable
    ? 0
    : Math.abs(state.sentiment.sentimentVelocity) * 15;
  return Math.max(
    0,
    Math.min(100, residualBoost + bsadfBoost + lpplsBoost + sentimentBoost)
  );
}

function toUnix(iso: string): number {
  const s = String(iso).slice(0, 10);
  // Force UTC midnight so scrubber dates do not shift by local timezone.
  return Math.floor(Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / 1000);
}

function historiesFromLayers(layers: LayerRows, cash = false) {
  const dlinear = layers.dlinear ?? [];
  const bsadf = layers.bsadf ?? [];
  const lppls = layers.lppls ?? [];
  const sentiment = layers.sentiment ?? [];
  const regime = layers.regime ?? [];

  const byDate = new Map<string, AssetState>();
  for (const row of dlinear) {
    const d = rowDateKey(row);
    if (!d) continue;
    byDate.set(d, {
      ...defaultAssetState,
      dlinear: {
        trend: Number(row.trend ?? 100),
        residual: Number(row.residual ?? 0),
        residualZ: Number(row.residual_z ?? row.residualZ ?? 0),
      },
    });
  }
  for (const row of bsadf) {
    const d = rowDateKey(row);
    const cur = byDate.get(d) ?? { ...defaultAssetState };
    byDate.set(d, {
      ...cur,
      bsadf: {
        bsadfStat: Number(row.bsadf_stat ?? row.bsadfStat ?? 0),
        criticalValue: Number(row.critical_value ?? row.criticalValue ?? 1.49),
        bubbleFlag: Boolean(row.bubble_flag ?? row.bubbleFlag ?? false),
      },
    });
  }
  for (const row of lppls) {
    const d = rowDateKey(row);
    const cur = byDate.get(d) ?? { ...defaultAssetState };
    const tcRaw = row.tc_estimate ?? row.tcEstimate;
    const startRaw = row.crash_window_start ?? row.crashWindowStart ?? tcRaw;
    const endRaw = row.crash_window_end ?? row.crashWindowEnd ?? tcRaw;
    byDate.set(d, {
      ...cur,
      lppls: {
        lppConfidence: Number(row.lpp_confidence ?? row.lppConfidence ?? 0),
        crashWindowStart: startRaw ? new Date(String(startRaw)) : null,
        crashWindowEnd: endRaw ? new Date(String(endRaw)) : null,
        unavailable: Boolean(row.unavailable ?? false),
        tcEstimate: tcRaw ? new Date(String(tcRaw)) : null,
      },
    });
  }
  for (const row of sentiment) {
    const d = rowDateKey(row);
    const cur = byDate.get(d) ?? { ...defaultAssetState };
    byDate.set(d, {
      ...cur,
      sentiment: {
        sentimentVelocity: Number(row.sentiment_velocity ?? row.sentimentVelocity ?? 0),
        sentimentLevel: Number(row.sentiment_level ?? row.sentimentLevel ?? 0),
        unavailable: Boolean(row.unavailable ?? true),
      },
    });
  }
  for (const row of regime) {
    const d = rowDateKey(row);
    const cur = byDate.get(d) ?? { ...defaultAssetState };
    byDate.set(d, {
      ...cur,
      regime: {
        regimeState: String(row.regime_state ?? row.regimeState ?? "normal") as
          | "normal"
          | "boom"
          | "bust",
        regimeConfidence: Number(row.regime_confidence ?? row.regimeConfidence ?? 0.5),
        boomProbability: Number(row.boom_probability ?? row.boomProbability ?? 0.1),
        bustProbability: Number(row.bust_probability ?? row.bustProbability ?? 0.1),
      },
    });
  }

  const dates = [...byDate.keys()].sort();
  const scoreHistory: TimeValuePoint[] = dates.map((d) => ({
    time: toUnix(d),
    value: cash ? 0 : Number(bubbleScoreFromState(byDate.get(d)!).toFixed(1)),
  }));

  const bsadfHistory: BSADFPoint[] = bsadf.map((row) => ({
    time: toUnix(String(row.as_of)),
    stat: Number(row.bsadf_stat ?? row.bsadfStat ?? 0),
    cv: Number(row.critical_value ?? row.criticalValue ?? 1.49),
  }));

  const lpplsHistory: LPPLSPoint[] = lppls
    .filter((row) => !row.unavailable)
    .map((row) => {
      const conf = Number(row.lpp_confidence ?? row.lppConfidence ?? 0);
      const tcRaw = row.tc_estimate ?? row.tcEstimate;
      return {
        time: toUnix(String(row.as_of)),
        confidence: Number.isFinite(conf) ? conf : 0,
        tcEstimate: tcRaw ? toUnix(String(tcRaw)) : null,
      };
    });

  const sentimentHistory: TimeValuePoint[] = sentiment
    .filter((row) => !row.unavailable)
    .map((row) => ({
      time: toUnix(String(row.as_of)),
      value: Number(row.sentiment_velocity ?? row.sentimentVelocity ?? 0),
    }));

  return { scoreHistory, bsadfHistory, lpplsHistory, sentimentHistory };
}

function stateFromLayerTip(layers: LayerRows, asOfUnix: number): AssetState {
  const tip = (rows: Array<Record<string, unknown>> | undefined) => {
    if (!rows?.length) return null;
    const eligible = rows.filter((r) => toUnix(String(r.as_of)) <= asOfUnix);
    return (eligible.length ? eligible[eligible.length - 1] : null) as Record<
      string,
      unknown
    > | null;
  };
  const d = tip(layers.dlinear);
  const b = tip(layers.bsadf);
  const l = tip(layers.lppls);
  const s = tip(layers.sentiment);
  const r = tip(layers.regime);

  return {
    dlinear: {
      trend: Number(d?.trend ?? 100),
      residual: Number(d?.residual ?? 0),
      residualZ: Number(d?.residual_z ?? d?.residualZ ?? 0),
    },
    bsadf: {
      bsadfStat: Number(b?.bsadf_stat ?? b?.bsadfStat ?? 0),
      criticalValue: Number(b?.critical_value ?? b?.criticalValue ?? 1.49),
      bubbleFlag: Boolean(b?.bubble_flag ?? b?.bubbleFlag ?? false),
    },
    lppls: (() => {
      const tcRaw = l?.tc_estimate ?? l?.tcEstimate;
      const startRaw = l?.crash_window_start ?? l?.crashWindowStart ?? tcRaw;
      const endRaw = l?.crash_window_end ?? l?.crashWindowEnd ?? tcRaw;
      return {
        lppConfidence: Number(l?.lpp_confidence ?? l?.lppConfidence ?? 0),
        crashWindowStart: startRaw ? new Date(String(startRaw)) : null,
        crashWindowEnd: endRaw ? new Date(String(endRaw)) : null,
        unavailable: Boolean(l?.unavailable ?? false),
        tcEstimate: tcRaw ? new Date(String(tcRaw)) : null,
      };
    })(),
    sentiment: {
      sentimentVelocity: Number(s?.sentiment_velocity ?? s?.sentimentVelocity ?? 0),
      sentimentLevel: Number(s?.sentiment_level ?? s?.sentimentLevel ?? 0),
      unavailable: Boolean(s?.unavailable ?? true),
    },
    regime: {
      regimeState: String(r?.regime_state ?? r?.regimeState ?? "normal") as
        | "normal"
        | "boom"
        | "bust",
      regimeConfidence: Number(r?.regime_confidence ?? r?.regimeConfidence ?? 0.5),
      boomProbability: Number(r?.boom_probability ?? r?.boomProbability ?? 0.1),
      bustProbability: Number(r?.bust_probability ?? r?.bustProbability ?? 0.1),
    },
  };
}

interface MarketStore {
  currentAsset: string;
  setCurrentAsset: (asset: string) => void;
  assetStates: Record<string, AssetState>;
  getAssetState: (asset: string) => AssetState;
  interpolated: Interpolated;
  bubbleScore: number;
  updateDLinear: (asset: string, data: DLinearState) => void;
  updateBSADF: (asset: string, data: BSADFState) => void;
  updateLPPLS: (asset: string, data: LPPLSState) => void;
  updateSentiment: (asset: string, data: SentimentState) => void;
  updateRegime: (asset: string, data: RegimeState) => void;
  onBubbleConfirmed: (asset: string) => void;
  onCrashWindowEntered: (asset: string) => void;
  onRegimeFlip: (asset: string, from: string, to: string) => void;
  connected: boolean;
  setConnected: (connected: boolean) => void;
  scoreHistory: TimeValuePoint[];
  bsadfHistory: BSADFPoint[];
  lpplsHistory: LPPLSPoint[];
  sentimentHistory: TimeValuePoint[];
  historyLoaded: boolean;
  historyAsset: string | null;
  historySource: "api" | "static" | "fixture" | "empty";
  rawLayers: LayerRows;
  loadHistoryFromApi: (
    asset: string,
    layers: LayerRows,
    source?: "api" | "static"
  ) => void;
  ensureFixtureHistories: () => void;
  clearHistories: () => void;
  applyAsOf: (asset: string, dateIso: string) => void;
  jumpToEpisode: (dateIso: string) => void;
  replayMode: boolean;
  replayTimestamp: number | null;
  setReplayMode: (enabled: boolean) => void;
  setReplayTimestamp: (ts: number) => void;
  lastUpdate: string;
  setLastUpdate: (iso: string) => void;
  enableWorld3d: boolean;
}

function refreshBubbleScore(get: () => MarketStore, set: (p: Partial<MarketStore>) => void) {
  const asset = get().currentAsset;
  const state = get().getAssetState(asset);
  set({ bubbleScore: bubbleScoreFromState(state) });
}

export const useMarketStore = create<MarketStore>((set, get) => ({
  currentAsset: "SP500_TOTAL_RETURN",
  setCurrentAsset: (asset) => {
    const same = get().historyAsset === asset;
    set({
      currentAsset: asset,
      // Drop the previous book's rows until this book's history arrives.
      ...(same
        ? {}
        : {
            historyAsset: null,
            rawLayers: {},
            scoreHistory: [],
            bsadfHistory: [],
            lpplsHistory: [],
            sentimentHistory: [],
            historyLoaded: false,
          }),
    });
    refreshBubbleScore(get, set);
  },
  assetStates: {
    SP500_TOTAL_RETURN: { ...defaultAssetState },
  },
  getAssetState: (asset) => get().assetStates[asset] || { ...defaultAssetState },
  interpolated: {
    terrainHeight: 100,
    terrainBumpiness: 0,
    obeliskGlow: 0,
    riftIntensity: 0,
    shimmerStrength: 0,
    crowdMomentum: 0,
  },
  bubbleScore: 0,
  updateDLinear: (asset, data) => {
    if (get().replayMode && get().historyLoaded) return;
    const current = get().assetStates[asset] || { ...defaultAssetState };
    set({
      assetStates: { ...get().assetStates, [asset]: { ...current, dlinear: data } },
      lastUpdate: new Date().toISOString(),
    });
    if (asset === get().currentAsset) {
      gsap.to(get().interpolated, {
        terrainHeight: data.trend,
        terrainBumpiness: Math.abs(data.residualZ),
        duration: 1.5,
        ease: "power2.out",
      });
      refreshBubbleScore(get, set);
    }
  },
  updateBSADF: (asset, data) => {
    if (get().replayMode && get().historyLoaded) return;
    const current = get().assetStates[asset] || { ...defaultAssetState };
    set({
      assetStates: { ...get().assetStates, [asset]: { ...current, bsadf: data } },
      lastUpdate: new Date().toISOString(),
    });
    if (asset === get().currentAsset) {
      const normalizedGlow = Math.max(
        0,
        (data.bsadfStat - data.criticalValue) / Math.max(data.criticalValue, 1e-6)
      );
      gsap.to(get().interpolated, {
        obeliskGlow: normalizedGlow,
        duration: 2.0,
        ease: "power1.out",
      });
      refreshBubbleScore(get, set);
    }
  },
  updateLPPLS: (asset, data) => {
    if (get().replayMode && get().historyLoaded) return;
    const current = get().assetStates[asset] || { ...defaultAssetState };
    set({
      assetStates: { ...get().assetStates, [asset]: { ...current, lppls: data } },
      lastUpdate: new Date().toISOString(),
    });
    if (asset === get().currentAsset) {
      gsap.to(get().interpolated, {
        riftIntensity: data.lppConfidence,
        duration: 2.0,
        ease: "power2.out",
      });
      refreshBubbleScore(get, set);
    }
  },
  updateSentiment: (asset, data) => {
    if (get().replayMode && get().historyLoaded) return;
    const current = get().assetStates[asset] || { ...defaultAssetState };
    set({
      assetStates: {
        ...get().assetStates,
        [asset]: { ...current, sentiment: data },
      },
      lastUpdate: new Date().toISOString(),
    });
    if (asset === get().currentAsset) {
      gsap.to(get().interpolated, {
        shimmerStrength: data.unavailable ? 0 : Math.abs(data.sentimentVelocity),
        duration: 1.0,
        ease: "linear",
      });
      refreshBubbleScore(get, set);
    }
  },
  updateRegime: (asset, data) => {
    if (get().replayMode && get().historyLoaded) return;
    const current = get().assetStates[asset] || { ...defaultAssetState };
    set({
      assetStates: { ...get().assetStates, [asset]: { ...current, regime: data } },
      lastUpdate: new Date().toISOString(),
    });
    if (asset === get().currentAsset) {
      const momentum =
        data.regimeState === "boom"
          ? data.boomProbability
          : data.regimeState === "bust"
            ? -data.bustProbability
            : 0;
      gsap.to(get().interpolated, {
        crowdMomentum: momentum,
        duration: 1.5,
        ease: "power2.inOut",
      });
    }
  },
  onBubbleConfirmed: (asset) => {
    console.log(`BUBBLE CONFIRMED: ${asset}`);
  },
  onCrashWindowEntered: (asset) => {
    console.log(`CRASH WINDOW ENTERED: ${asset}`);
  },
  onRegimeFlip: (asset, from, to) => {
    console.log(`REGIME FLIP: ${asset} ${from} -> ${to}`);
  },
  connected: false,
  setConnected: (connected) => set({ connected }),
  scoreHistory: [],
  bsadfHistory: [],
  lpplsHistory: [],
  sentimentHistory: [],
  historyLoaded: false,
  historyAsset: null,
  historySource: "empty",
  rawLayers: {},
  loadHistoryFromApi: (asset, layers, source = "api") => {
    const built = historiesFromLayers(layers, asset === "US_CASH_RETURN");
    if (!built.scoreHistory.length) {
      get().clearHistories();
      return;
    }
    const tipUnix = built.scoreHistory[built.scoreHistory.length - 1].time;
    // A pinned date must survive switching books, or the homepage scrubber jumps to the tip.
    const kept =
      get().replayMode && get().replayTimestamp != null
        ? get().replayTimestamp
        : null;
    const pinUnix = kept ?? tipUnix;
    const tipState = stateFromLayerTip(layers, pinUnix);
    set({
      currentAsset: asset,
      historyAsset: asset,
      rawLayers: layers,
      scoreHistory: built.scoreHistory,
      bsadfHistory: built.bsadfHistory,
      lpplsHistory: built.lpplsHistory,
      sentimentHistory: built.sentimentHistory,
      historyLoaded: true,
      historySource: source,
      assetStates: { ...get().assetStates, [asset]: tipState },
      bubbleScore: asset === "US_CASH_RETURN" ? 0 : bubbleScoreFromState(tipState),
      lastUpdate: new Date(pinUnix * 1000).toISOString(),
      replayMode: true,
      replayTimestamp: pinUnix,
    });
  },
  clearHistories: () => {
    set({
      scoreHistory: [],
      bsadfHistory: [],
      lpplsHistory: [],
      sentimentHistory: [],
      historyLoaded: false,
      historySource: "empty",
      rawLayers: {},
    });
  },
  ensureFixtureHistories: () => {
    // Refuse seedHistories when real tape already loaded.
    if (get().historySource === "api" || get().historySource === "static") return;
    if (get().historyLoaded) return;
    // Empty-state product path: no silent sine-wave charts.
    get().clearHistories();
  },
  applyAsOf: (asset, dateIso) => {
    const layers = get().rawLayers;
    if (!Object.keys(layers).length) return;
    const snapped = snapAsOfIso(layers, dateIso);
    if (!snapped) return;
    const unix = toUnix(snapped);
    const tipState = stateFromLayerTip(layers, unix);
    // Refuse empty tip (before tape start) - snapAsOfIso already guards this.
    set({
      assetStates: { ...get().assetStates, [asset]: tipState },
      bubbleScore: asset === "US_CASH_RETURN" ? 0 : bubbleScoreFromState(tipState),
      lastUpdate: `${snapped}T00:00:00.000Z`,
      replayMode: true,
      replayTimestamp: unix,
    });
  },
  jumpToEpisode: (dateIso) => {
    get().applyAsOf(get().currentAsset, dateIso);
  },
  replayMode: false,
  replayTimestamp: null,
  setReplayMode: (enabled) =>
    set({
      replayMode: enabled,
      replayTimestamp: enabled
        ? get().scoreHistory[get().scoreHistory.length - 1]?.time ?? null
        : null,
    }),
  setReplayTimestamp: (ts) => set({ replayTimestamp: ts, replayMode: true }),
  lastUpdate: new Date().toISOString(),
  setLastUpdate: (iso) => set({ lastUpdate: iso }),
  enableWorld3d: import.meta.env.VITE_ENABLE_WORLD_3D === "true",
}));
