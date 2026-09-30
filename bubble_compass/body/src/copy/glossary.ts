/**
 * Sensational display terms; technical names live in `tech` for hover only.
 */

export type GlossaryEntry = {
  label: string;
  valueHint?: string;
  tech: string;
};

export const glossary = {
  bubbleScore: {
    label: "Overheat Alert",
    tech: "Bubble Score (0-100). Mixes DLinear residual z-score, PSY/BSADF stretch vs critical value, LPPLS confidence, and FinBERT sentiment velocity when available.",
  },
  heatLow: {
    label: "All Clear",
    tech: "Heat below 40. Residual and bubble tests sit near quiet baselines.",
  },
  heatWarm: {
    label: "Warming Up",
    tech: "Heat 40-69. Price stretch or crash-timing confidence is rising.",
  },
  heatHot: {
    label: "Overheat Alert",
    tech: "Heat 70-100. Several layers agree the move looks explosive or late-stage.",
  },
  regime: {
    label: "Market state",
    tech: "Regime from the RL classifier (heuristic fallback when no PPO model is loaded): normal, boom, or bust.",
  },
  regimeNormal: {
    label: "All Clear",
    tech: "Regime = normal. Boom and bust probabilities stay low.",
  },
  regimeBoom: {
    label: "FRENZY MODE",
    tech: "Regime = boom. Stretch and hype features point to crowded upside.",
  },
  regimeBust: {
    label: "COLLAPSE WARNING",
    tech: "Regime = bust. Crash-window and downside features dominate.",
  },
  stretchTest: {
    label: "Explosive Growth Detected",
    tech: "PSY BSADF (Phillips-Shi-Yu Backward Sup-ADF). Compares the explosive-growth statistic to a critical value under a random-walk null.",
  },
  crashTiming: {
    label: "Crash Window Opening",
    tech: "LPPLS (Log-Periodic Power Law Singularity). Multi-window fit confidence and the estimated critical-time window (tc).",
  },
  newsTone: {
    label: "Hype Meter",
    tech: "FinBERT sentiment. Level is average headline polarity (-1 to +1). Rate is sentiment velocity. Marked unavailable when no headlines are wired.",
  },
  heatHistory: {
    label: "Overheat over time",
    tech: "Historical Bubble Score series with threshold lines at 40 (warming) and 70 (hot).",
  },
  scrubHistory: {
    label: "Scrub history",
    tech: "Point-in-time replay from expanding-window parquet. Charts and the as-of stamp follow the scrubber; live WebSocket updates pause while scrubbing.",
  },
  overview: {
    label: "Overview",
    tech: "Primary quant view: overheat alert, market state, and evidence charts on the history tape.",
  },
  world: {
    label: "World",
    tech: "Experimental 3D marketscape behind VITE_ENABLE_WORLD_3D. Terrain maps the same layer outputs.",
  },
  game: {
    label: "Game",
    tech: "As-Of Desk: play the same history tape. One real session per turn; no synthetic event generator.",
  },
  live: {
    label: "Live",
    tech: "WebSocket connected. Dashboard fields update from the brain feed.",
  },
  offline: {
    label: "Offline",
    tech: "No live WebSocket. Showing cached history or fixture state.",
  },
  scrubbing: {
    label: "Scrubbing",
    tech: "Replay mode. The scrubber owns the as-of date; live deltas are ignored.",
  },
  asOf: {
    label: "As of",
    tech: "Decision timestamp in America/New_York, with UTC clock beside it.",
  },
  evidence: {
    label: "Checks",
    tech: "One-line readouts from Layers 2-4 (BSADF, LPPLS, FinBERT).",
  },
  crisisAlert: {
    label: "Crisis alert",
    tech: "Full-width banner when Overheat Alert exceeds 70 on the selected as-of date.",
  },
  story: {
    label: "Story",
    tech: "Narrative of the selected as-of: what Heat, stretch, and crash-window already showed that morning.",
  },
} as const satisfies Record<string, GlossaryEntry>;

export type GlossaryKey = keyof typeof glossary;

export function heatBandLabel(score: number): GlossaryKey {
  if (score < 40) return "heatLow";
  if (score < 70) return "heatWarm";
  return "heatHot";
}

export function regimeKey(
  regime: "normal" | "boom" | "bust"
): "regimeNormal" | "regimeBoom" | "regimeBust" {
  if (regime === "boom") return "regimeBoom";
  if (regime === "bust") return "regimeBust";
  return "regimeNormal";
}
