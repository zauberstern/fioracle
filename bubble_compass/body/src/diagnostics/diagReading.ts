import type { BookReading } from "../narrator/scoreCopy";
import { heatClose, playChangeSentence } from "../narrator/scoreCopy";

export function oddsPercent(value: unknown): number | null {
  if (value == null || !Number.isFinite(Number(value))) return null;
  const n = Number(value);
  return n <= 1 ? Math.round(n * 100) : Math.round(n);
}

function regimeLine(
  boom: number | null,
  bust: number | null,
  prevBoom: number | null,
  prevBust: number | null
): string {
  const same =
    boom != null &&
    bust != null &&
    boom === prevBoom &&
    bust === prevBust;
  if (same) {
    return "Boom and bust match the prior row. The recorded state stays normal.";
  }
  if (boom == null || bust == null) {
    return "The recorded state stays normal.";
  }
  return `Boom is ${boom} percent and bust is ${bust} percent. The recorded state stays normal.`;
}

const IDLE =
  "A date for a break and news tone are not in this history, so each adds 0.";

const CASH_CHART =
  "The stretch chart marks cash as stretched on every row in this history. Heat stays at 0.";

export function diagLines(args: {
  name: string;
  cash?: boolean;
  now: BookReading;
  prev: { word: string; heat: number } | null;
  nowDate: string;
  prevDate: string;
  boom: number | null;
  bust: number | null;
  prevBoom: number | null;
  prevBust: number | null;
}): string[] {
  const change = playChangeSentence({
    name: args.name,
    cash: args.cash,
    now: { word: args.now.word, heat: args.now.heat },
    prev: args.prev,
    nowDate: args.nowDate,
    prevDate: args.prevDate,
  });
  const regime = regimeLine(args.boom, args.bust, args.prevBoom, args.prevBust);
  if (args.cash) {
    return [
      change,
      heatClose(args.name, args.now.parts, true),
      CASH_CHART,
      regime,
      IDLE,
    ];
  }
  const path = args.now.lines[0] ?? "";
  const rise = args.now.lines[1] ?? "";
  return [change, path, rise, regime, IDLE];
}
