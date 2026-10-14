import { plainDate } from "../../../shared/plainDate";
import {
  heatParts,
  rowBefore,
  rowOnOrBefore,
  statusWord,
  tipFromLayerRows,
  type HeatParts,
  type StatusWord,
  type TipLayers,
} from "./heat";

export type { HeatParts };

type LayerBundle = Record<string, Array<Record<string, unknown>>>;

export type BookReading = {
  heat: number;
  word: StatusWord;
  parts: HeatParts;
  lines: string[];
  move: string;
  dailyReturn: number | null;
  flag: boolean;
};

export const MACHINERY: readonly string[] = [
  "Heat is a score from 0 to 100 for how unusual a book's recent rise looks. Four parts are added, then the score stops at 100.",
  "The first part is how many steps the book sits above the path it had been following. That distance adds 12 points per unit and this part stops at 40.",
  "The second part asks whether the rise is speeding up. When the fast-rise check is on, that part starts at 25 and adds 8 points for each unit past the ordinary line, 1.49.",
  "A date for a break can add 30 points. News tone can add 15 points times how fast that tone is changing. On this history both are missing, so each adds 0.",
  "A new row arrives about every 21 business days. The fast-rise check is on when the reading is past the ordinary line.",
];

function points(n: number): string {
  return n.toFixed(1);
}

/** A coarse screen can print a huge reading. The score still stops at 100. */
function plainReading(n: number): string {
  if (Math.abs(n) >= 100) return Math.round(n).toLocaleString("en-US");
  return n.toFixed(2);
}

function num(n: number): string {
  return n.toFixed(2);
}

function bps(n: number): string {
  const rounded = Math.round(n * 100) / 100;
  if (Math.abs(rounded - Math.round(rounded)) < 1e-9) {
    return String(Math.round(rounded));
  }
  return rounded.toFixed(2);
}

export function driverSentence(tip: TipLayers): string {
  const parts = heatParts(tip);
  const cv = tip.criticalValue ?? 1.49;
  const flag = tip.bubbleFlag ? "on" : "off";
  const stretch =
    parts.bsadf > 100
      ? `An ordinary rise stays near ${num(cv)}, and this reading is ${plainReading(tip.bsadfStat ?? 0)}, so the score stops at 100.`
      : `The fast-rise reading is ${plainReading(tip.bsadfStat ?? 0)}, against an ordinary line of ${num(cv)}. The check is ${flag}, which adds ${points(parts.bsadf)} points.`;
  let idle = "";
  if (tip.lpplsUnavailable && tip.sentimentUnavailable) {
    idle = " A break date and news tone are not in this history, so they add 0.";
  } else if (tip.lpplsUnavailable) {
    idle = " A break date is not in this history, so that part adds 0.";
  } else if (tip.sentimentUnavailable) {
    idle = " News tone is not in this history, so that part adds 0.";
  }
  const z = tip.residualZ ?? 0;
  const side = z < 0 ? "below" : "above";
  return `It sits ${num(Math.abs(z))} steps ${side} the path it had been following, which adds ${points(parts.residual)} points. ${stretch}${idle}`;
}

export function pieceLines(tip: TipLayers, parts: HeatParts): string[] {
  const cv = tip.criticalValue ?? 1.49;
  const flag = tip.bubbleFlag ? "on" : "off";
  const crash = tip.lpplsUnavailable
    ? "A date for a break is not in this history, so that part adds 0."
    : `The chance of a dated break is ${num(tip.lppConfidence ?? 0)}, which adds ${points(parts.lppls)} points.`;
  const tone = tip.sentimentUnavailable
    ? "News tone is not in this history, so that part adds 0."
    : `News tone is changing at ${num(tip.sentimentVelocity ?? 0)}, which adds ${points(parts.sentiment)} points.`;
  const stretch =
    parts.bsadf > 100
      ? `The fast-rise reading is ${plainReading(tip.bsadfStat ?? 0)}, far above an ordinary line of ${num(cv)}. The check is ${flag}, so the score stops at 100.`
      : `The fast-rise reading is ${plainReading(tip.bsadfStat ?? 0)}, against an ordinary line of ${num(cv)}. The check is ${flag}, which adds ${points(parts.bsadf)} points.`;
  return [
    `It sits ${num(Math.abs(tip.residualZ ?? 0))} steps ${(tip.residualZ ?? 0) < 0 ? "below" : "above"} the path it had been following. That adds ${points(parts.residual)} points.`,
    stretch,
    crash,
    tone,
  ];
}

const MOVERS: Array<[keyof HeatParts, string]> = [
  ["residual", "The distance above its path"],
  ["bsadf", "The fast-rise check"],
  ["lppls", "A break date"],
  ["sentiment", "News tone"],
];

export function moveSentence(
  now: HeatParts,
  prev: HeatParts | null,
  dailyReturn: number | null
): string {
  const zero =
    dailyReturn === 0 ? " The book's return on this row is 0." : "";
  if (!prev) return "There is no earlier row on this book.";
  let bestName = "";
  let bestDelta = 0;
  for (const [key, label] of MOVERS) {
    const delta = now[key] - prev[key];
    if (Math.abs(delta) > Math.abs(bestDelta) + 1e-9) {
      bestDelta = delta;
      bestName = label;
    }
  }
  if (Math.abs(bestDelta) < 0.05) {
    return `The four parts match the prior row.${zero}`;
  }
  const dir = bestDelta > 0 ? "up" : "down";
  return `${bestName} moved ${dir} by ${Math.abs(bestDelta).toFixed(1)} points from the prior row.${zero}`;
}

export function sharedMarkSentences(row: {
  asOf: string;
  hyBps: number | null;
  hyChange: number | null;
  vix: number | null;
  debt: number | null;
  gap: number | null;
  breach: boolean | null;
}): string[] {
  const lines: string[] = [];
  if (row.hyBps != null && Number.isFinite(row.hyBps)) {
    let line = `The high-yield spread on this row is ${bps(row.hyBps)} basis points.`;
    if (row.hyChange != null && Number.isFinite(row.hyChange)) {
      line += ` The 20-day change is ${bps(row.hyChange)} basis points.`;
    }
    if (row.asOf.slice(0, 10) >= "2022-02-01") {
      line +=
        " The unit of that spread changes around 1 Feb 2022, and after that the series is unchanged.";
    }
    lines.push(line);
  }
  if (row.vix != null && Number.isFinite(row.vix)) {
    lines.push(`VIX on this row is ${row.vix.toFixed(2)}.`);
  }
  if (row.debt != null && Number.isFinite(row.debt)) {
    const gap =
      row.gap != null && Number.isFinite(row.gap)
        ? ` The gap is ${row.gap.toFixed(2)}.`
        : "";
    const breach =
      row.breach == null
        ? ""
        : row.breach
          ? " The threshold is breached."
          : " The threshold is not breached.";
    lines.push(
      `US debt on this row is ${row.debt.toFixed(2)} percent of GDP.${gap}${breach}`
    );
  }
  return lines;
}

export function bookMarkSentence(
  name: string,
  parts: HeatParts,
  flag: boolean
): string {
  const word = statusWord(parts.heat);
  const flagWord = flag ? "on" : "off";
  const stretch =
    parts.bsadf > 100
      ? "The fast-rise check is on, and the score stops at 100."
      : `The fast-rise check is ${flagWord} and adds ${points(parts.bsadf)}.`;
  return `${name} heat is ${points(parts.heat)}, ${word}. The distance above its path adds ${points(parts.residual)}. ${stretch} ${name} is a total return.`;
}

function sumText(n: number): string {
  if (Math.abs(n) >= 100) {
    return n.toLocaleString("en-US", { maximumFractionDigits: 1 });
  }
  return n.toFixed(1);
}

export function heatClose(
  name: string,
  parts: HeatParts,
  cash?: boolean
): string {
  if (cash) {
    return `${name} is held at heat 0, so it stays out of the ranking.`;
  }
  const raw = parts.residual + parts.bsadf + parts.lppls + parts.sentiment;
  const word = statusWord(parts.heat);
  const shown = parts.heat.toFixed(1);
  if (raw - parts.heat > 0.05) {
    return `The four parts add to ${sumText(raw)}. Heat stops at 100, so ${name} reads ${word} at ${shown}.`;
  }
  return `The four parts add to ${shown}. ${name} reads ${word}.`;
}

export function spineSentence(
  bookCount: number,
  rowCount: number,
  firstIso: string,
  lastIso: string
): string {
  return `From ${plainDate(firstIso)} through ${plainDate(lastIso)}, this history has ${bookCount} books and ${rowCount} rows.`;
}

export function playChangeSentence(args: {
  name: string;
  cash?: boolean;
  now: { word: string; heat: number };
  prev: { word: string; heat: number } | null;
  nowDate: string;
  prevDate: string;
}): string {
  const nowDate = plainDate(args.nowDate);
  const heat = args.now.heat.toFixed(1);
  if (args.cash) {
    return `Cash on ${nowDate} is left out and stays at 0.`;
  }
  if (!args.prev || !args.prevDate) {
    return `${nowDate} is the first row for ${args.name}. It reads ${args.now.word} at ${heat}.`;
  }
  const prevDate = plainDate(args.prevDate);
  const prevHeat = args.prev.heat.toFixed(1);
  if (args.now.word === args.prev.word && args.now.heat.toFixed(1) === prevHeat) {
    return `From ${prevDate} to ${nowDate}, ${args.name} stayed ${args.now.word} at ${heat}.`;
  }
  return `From ${prevDate} to ${nowDate}, ${args.name} went from ${args.prev.word} at ${prevHeat} to ${args.now.word} at ${heat}.`;
}

export function padSentence(returns: Array<number | null>): string | null {
  const nums = returns.filter(
    (r): r is number => r != null && Number.isFinite(r)
  );
  if (nums.length === 0 || nums.some((r) => r !== 0)) return null;
  return "On this row, every loaded book has a return of 0. Where the row repeats an earlier print, that zero is a placeholder.";
}

function finiteReturn(row: Record<string, unknown> | null): number | null {
  if (!row || row.daily_return == null) return null;
  const n = Number(row.daily_return);
  return Number.isFinite(n) ? n : null;
}

export function readBook(
  book: { name: string; cash?: boolean },
  layers: LayerBundle | undefined,
  asOf: string | undefined
): BookReading {
  const empty: HeatParts = {
    residual: 0,
    bsadf: 0,
    lppls: 0,
    sentiment: 0,
    heat: 0,
  };
  if (!layers) {
    return {
      heat: 0,
      word: "Quiet",
      parts: empty,
      lines: ["This book's history is still loading."],
      move: "",
      dailyReturn: null,
      flag: false,
    };
  }
  const tip = tipFromLayerRows(layers, asOf);
  const parts = heatParts(tip, { cash: book.cash });
  const dRows = layers.dlinear ?? [];
  const dHit = asOf
    ? rowOnOrBefore(dRows, asOf)
    : (dRows[dRows.length - 1] ?? null);
  const dailyReturn = finiteReturn(dHit);
  if (book.cash) {
    return {
      heat: 0,
      word: "Quiet",
      parts,
      lines: ["Cash is left out of the ranking. Its score stays at 0."],
      move: "",
      dailyReturn,
      flag: Boolean(tip.bubbleFlag),
    };
  }
  const prior = asOf
    ? rowBefore(dRows, asOf)
    : dRows.length >= 2
      ? dRows[dRows.length - 2]
      : null;
  const prevParts = prior
    ? heatParts(tipFromLayerRows(layers, String(prior.as_of ?? "")))
    : null;
  return {
    heat: parts.heat,
    word: statusWord(parts.heat),
    parts,
    lines: pieceLines(tip, parts),
    move: moveSentence(parts, prevParts, dailyReturn),
    dailyReturn,
    flag: Boolean(tip.bubbleFlag),
  };
}
