import type { StatusWord } from "./heat";

export type BookMove = {
  id: string;
  name: string;
  group: string;
  cash?: boolean;
  ret: number | null;
  trail: number[];
};

export type CategorySlice = { group: string; pct: number };

export type MixPie = {
  slices: CategorySlice[];
  delta: number | null;
};

export type RankedBasket = {
  cash: { name: string; delta: number } | null;
  best: MixPie;
  smooth: MixPie;
  worst: MixPie;
};

export function dollarDelta(amount: number, ret: number | null): number | null {
  if (ret == null || !Number.isFinite(ret) || !Number.isFinite(amount)) return null;
  return amount * ret;
}

export function trailReturns(
  rows: Array<Record<string, unknown>>,
  asOf: string,
  k = 6
): number[] {
  const pin = asOf.slice(0, 10);
  const out: number[] = [];
  for (const row of rows) {
    const day = String(row.as_of ?? "").slice(0, 10);
    if (!day || day > pin) continue;
    if (row.daily_return == null) continue;
    const n = Number(row.daily_return);
    if (!Number.isFinite(n)) continue;
    out.push(n);
  }
  return out.slice(Math.max(0, out.length - k));
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function stdev(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  const varSum = xs.reduce((a, b) => a + (b - m) * (b - m), 0) / (xs.length - 1);
  return Math.sqrt(varSum);
}

function rideScore(trail: number[]): number | null {
  if (trail.length < 3) return null;
  const s = stdev(trail);
  if (s < 1e-12) return null;
  return mean(trail) / s;
}

function emptyPie(): MixPie {
  return { slices: [], delta: null };
}

function weightPie(
  live: BookMove[],
  amount: number,
  weightOf: (m: BookMove) => number
): MixPie {
  const scored = live
    .map((m) => ({ m, w: weightOf(m) }))
    .filter((x) => x.w > 0 && x.m.ret != null && Number.isFinite(x.m.ret));
  const totalW = scored.reduce((a, x) => a + x.w, 0);
  if (totalW <= 0) return emptyPie();

  const byGroup = new Map<string, number>();
  let portRet = 0;
  for (const { m, w } of scored) {
    const share = w / totalW;
    byGroup.set(m.group, (byGroup.get(m.group) ?? 0) + share);
    portRet += share * (m.ret as number);
  }
  const slices = [...byGroup.entries()]
    .map(([group, share]) => ({ group, pct: share * 100 }))
    .sort((a, b) => b.pct - a.pct || a.group.localeCompare(b.group));
  return { slices, delta: amount * portRet };
}

export function rankBasket(moves: BookMove[], amount: number): RankedBasket {
  const cashMove = moves.find((m) => m.cash);
  const cashDelta = cashMove ? dollarDelta(amount, cashMove.ret) : null;
  const live = moves.filter((m) => !m.cash && m.ret != null);
  return {
    cash:
      cashMove && cashDelta != null ? { name: cashMove.name, delta: cashDelta } : null,
    best: weightPie(live, amount, (m) => Math.max(0, m.ret ?? 0)),
    smooth: weightPie(live, amount, (m) => {
      const score = rideScore(m.trail);
      return score != null && score > 0 ? score : 0;
    }),
    worst: weightPie(live, amount, (m) => Math.max(0, -(m.ret ?? 0))),
  };
}

export function gistTag(input: {
  word: StatusWord;
  cashDelta: number;
  bestDelta: number;
  worstDelta: number;
  hotDelta: number | null;
}): string {
  const miss = input.bestDelta - input.cashDelta;
  const dodge = input.cashDelta - input.worstDelta;
  if (input.word === "Stretched") {
    if (input.hotDelta != null && input.hotDelta < 0) return "piano overhead";
    if (miss > Math.abs(input.cashDelta) && miss > 0) return "FOMO meter";
    if (dodge > 0 && input.worstDelta < 0) return "you sat this one";
    return "toasty";
  }
  if (input.word === "Warming") {
    if (miss > Math.max(1, Math.abs(input.cashDelta))) return "getting warm";
    return "warm seat";
  }
  if (miss > Math.max(1, Math.abs(input.cashDelta) * 2)) return "left on read";
  return "couch money";
}

function money(n: number): string {
  const abs = Math.abs(n);
  const body =
    abs >= 100
      ? abs.toLocaleString("en-US", { maximumFractionDigits: 0 })
      : abs.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return (n < 0 ? "-" : "") + body;
}

export function feelLine(input: {
  amount: number;
  currency: string;
  date: string;
  cashName: string;
  cashDelta: number;
  bestDelta: number;
  worstDelta: number;
  heat: number;
  word: StatusWord;
}): string {
  const pile = input.amount.toLocaleString("en-US");
  const miss = input.bestDelta - input.cashDelta;
  return (
    `On ${input.date}, ${pile} ${input.currency} in ${input.cashName} moved ${money(input.cashDelta)} this mark (direct). ` +
    `Heat ${input.heat} (${input.word}) marks books far above their path or rising fast; cash heat stays 0, so the indirect effect is missing the best group mix (${money(miss)} vs your pile) and dodging the worst mix (${money(input.worstDelta)}). ` +
    `Pies weight books by last-mark gain, by smooth ride, and by last-mark loss, then roll up to group %.`
  );
}

/** Stable colors for the investible groups on the cash card. */
export const GROUP_COLORS: Record<string, string> = {
  "US stocks": "#171a20",
  "US credit": "#6E442C",
  "US rates": "#0072B2",
  Commodities: "#A6764C",
  "World bonds": "#5C5E62",
  Swiss: "#393C41",
  Inflation: "#8E542F",
  Other: "#C4AD88",
  Cash: "#D0BA9B",
};

export function pieConic(slices: CategorySlice[]): string {
  if (!slices.length) return "conic-gradient(#d0d1d2 0 100%)";
  let at = 0;
  const parts: string[] = [];
  for (const s of slices) {
    const color = GROUP_COLORS[s.group] ?? "#5C5E62";
    const next = at + s.pct;
    parts.push(`${color} ${at}% ${next}%`);
    at = next;
  }
  if (at < 100) parts.push(`#d0d1d2 ${at}% 100%`);
  return `conic-gradient(${parts.join(", ")})`;
}
