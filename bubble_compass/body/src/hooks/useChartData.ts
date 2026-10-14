import { useMarketStore } from "../store/marketStore";

/** Map store series through the replay cursor when replay mode is active. */
export function useChartCutoff(): number | null {
  const replayMode = useMarketStore((s) => s.replayMode);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  if (!replayMode || replayTimestamp == null) return null;
  return replayTimestamp;
}

export function sliceByCutoff<T extends { time: number }>(
  data: T[],
  cutoff: number | null
): T[] {
  if (cutoff == null) return data;
  return data.filter((d) => d.time <= cutoff);
}

/** Lightweight Charts rejects duplicate or unsorted times. */
export function uniqueByTime<T extends { time: number }>(rows: T[]): T[] {
  const byTime = new Map<number, T>();
  for (const row of rows) byTime.set(row.time, row);
  return [...byTime.values()].sort((a, b) => a.time - b.time);
}

/** Chart ceiling so one huge reading does not hide the ordinary line at 1.49. */
export const FAST_RISE_PLOT_TOP = 8;

export function plotFastRise(stat: number): number {
  if (!Number.isFinite(stat)) return 0;
  return Math.min(stat, FAST_RISE_PLOT_TOP);
}

/** Look closer draws every row. Other charts can still stop at the pinned date. */
export function chartRows<T extends { time: number }>(
  data: T[],
  cutoff: number | null,
  fullSpan: boolean
): T[] {
  return uniqueByTime(sliceByCutoff(data, fullSpan ? null : cutoff));
}

export function rowAtPin<T extends { time: number }>(
  data: T[],
  pin: number | null
): T | null {
  if (!data.length) return null;
  if (pin == null) return data[data.length - 1] ?? null;
  let hit: T | null = null;
  for (const row of data) {
    if (row.time <= pin) hit = row;
  }
  return hit;
}
