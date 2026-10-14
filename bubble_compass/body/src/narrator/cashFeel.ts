import type { StatusWord } from "./heat";

export type BookMove = {
  id: string;
  name: string;
  group: string;
  cash?: boolean;
  ret: number | null;
  trail: number[];
};

export type RankedBasket = {
  cash: { name: string; delta: number } | null;
  best: { name: string; group: string; delta: number } | null;
  worst: { name: string; group: string; delta: number } | null;
  smooth: { name: string; group: string; score: number } | null;
  byGroup: Array<{ group: string; delta: number; name: string }>;
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

export function rankBasket(moves: BookMove[], amount: number): RankedBasket {
  const cashMove = moves.find((m) => m.cash);
  const cashDelta = cashMove ? dollarDelta(amount, cashMove.ret) : null;
  const live = moves.filter((m) => !m.cash && m.ret != null);
  let best: RankedBasket["best"] = null;
  let worst: RankedBasket["worst"] = null;
  let smooth: RankedBasket["smooth"] = null;
  for (const m of live) {
    const delta = dollarDelta(amount, m.ret);
    if (delta == null) continue;
    if (!best || delta > best.delta) best = { name: m.name, group: m.group, delta };
    if (!worst || delta < worst.delta) worst = { name: m.name, group: m.group, delta };
    const score = rideScore(m.trail);
    if (score != null && (!smooth || score > smooth.score)) {
      smooth = { name: m.name, group: m.group, score };
    }
  }
  const byGroupMap = new Map<string, { group: string; delta: number; name: string }>();
  for (const m of live) {
    const delta = dollarDelta(amount, m.ret);
    if (delta == null) continue;
    const prev = byGroupMap.get(m.group);
    if (!prev || delta > prev.delta) {
      byGroupMap.set(m.group, { group: m.group, delta, name: m.name });
    }
  }
  const byGroup = [...byGroupMap.values()].sort((a, b) => b.delta - a.delta);
  return {
    cash:
      cashMove && cashDelta != null ? { name: cashMove.name, delta: cashDelta } : null,
    best,
    worst,
    smooth,
    byGroup,
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
  bestName: string;
  bestDelta: number;
  bestGroup: string;
  smoothName: string;
  smoothGroup: string;
  worstName: string;
  worstDelta: number;
  worstGroup: string;
  heat: number;
  word: StatusWord;
}): string {
  const pile = input.amount.toLocaleString("en-US");
  return (
    `On ${input.date}, ${pile} ${input.currency} in ${input.cashName} moved ${money(input.cashDelta)} on the last tape mark. ` +
    `Best of the basket was ${input.bestName} (${input.bestGroup}), ${money(input.bestDelta)}. ` +
    `Smoothest ride was ${input.smoothName} in ${input.smoothGroup}. ` +
    `Worst was ${input.worstName} (${input.worstGroup}), ${money(input.worstDelta)}. ` +
    `Heat is ${input.heat}, ${input.word}. That score is how unusual a rise looks. The dollars are the last mark on this tape.`
  );
}
