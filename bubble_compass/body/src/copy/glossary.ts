/**
 * Public reading labels; technical names live in `tech` for Look closer hover.
 */

export type GlossaryEntry = {
  label: string;
  valueHint?: string;
  tech: string;
};

export const glossary = {
  bubbleScore: {
    label: "Heat",
    tech: "Heat runs from 0 to 100. It adds distance above the book's path and a fast-rise check, and it stops at 100.",
  },
  heatLow: {
    label: "Quiet",
    tech: "Heat below 40. Residual stretch and the bubble tests sit near a quiet baseline.",
  },
  heatWarm: {
    label: "Warming",
    tech: "Heat from 40 to 69. Upside stretch, or crash-timing confidence, is rising.",
  },
  heatHot: {
    label: "Stretched",
    tech: "Heat from 70 to 100. Several layers agree the upside move looks late. A large residual on its own is not treated as overheat.",
  },
  regime: {
    label: "Market state",
    tech: "The regime label is normal, boom, or bust. A heuristic fills in when no trained model is loaded.",
  },
  regimeNormal: {
    label: "Quiet",
    tech: "Regime is normal. Boom and bust probabilities stay low.",
  },
  regimeBoom: {
    label: "Warming",
    tech: "Regime is boom. Stretch features point at a crowded upside.",
  },
  regimeBust: {
    label: "Stretched",
    tech: "Regime is bust. Crash-window and downside features lead.",
  },
  stretchTest: {
    label: "Fast rise",
    tech: "PSY BSADF compares the explosive-growth statistic with a critical value under a random-walk null.",
  },
  crashTiming: {
    label: "Timing",
    tech: "LPPLS fit confidence and the estimated critical-time window. When the package is missing, the row says not estimated.",
  },
  newsTone: {
    label: "Headlines",
    tech: "FinBERT tone from headlines. This history marks the layer unavailable because no headlines are wired.",
  },
  heatHistory: {
    label: "Heat over time",
    tech: "Heat through the history, with lines at 40 (warming) and 70 (stretched).",
  },
  scrubHistory: {
    label: "Walk the record",
    tech: "Replay from the saved history. Charts and the date stamp follow the scrubber.",
  },
  overview: {
    label: "This week",
    tech: "The weekly page: Quiet, Warming, or Stretched, plus Heat on the public marks.",
  },
  world: {
    label: "World",
    tech: "An experimental 3D view behind VITE_ENABLE_WORLD_3D. It is off the public nav.",
  },
  game: {
    label: "Stillmoor",
    tech: "An optional town on the same history. Each stamp is one real session. There is no synthetic event generator.",
  },
  live: {
    label: "Saved history",
    tech: "The history comes from saved files or the API. With no socket, the page does not say Live.",
  },
  offline: {
    label: "Empty history",
    tech: "No history is loaded.",
  },
  scrubbing: {
    label: "Walk the record",
    tech: "Replay is on. The scrubber owns the date, and live deltas are ignored.",
  },
  asOf: {
    label: "Dated",
    tech: "The snapped as-of date on the history, at UTC midnight.",
  },
  evidence: {
    label: "Checks",
    tech: "Short readouts from the stretch test, crash timing, and headline tone.",
  },
  crisisAlert: {
    label: "Stretched",
    tech: "Shown when Heat is 70 or higher on the date you have pinned.",
  },
  story: {
    label: "The morning's read",
    tech: "What Heat, stretch, and the crash window already showed on that morning.",
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
