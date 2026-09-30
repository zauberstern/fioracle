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
