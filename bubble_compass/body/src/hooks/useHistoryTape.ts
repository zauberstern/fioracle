import { useEffect, useRef } from "react";
import { useMarketStore } from "../store/marketStore";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const HISTORY_BASE =
  import.meta.env.VITE_HISTORY_BASE ||
  `${import.meta.env.BASE_URL || "/"}data/`;

function historyJsonUrl(asset: string): string {
  const base = HISTORY_BASE.endsWith("/") ? HISTORY_BASE : `${HISTORY_BASE}/`;
  return `${base}history/${encodeURIComponent(asset)}.json`;
}

/** Load expanding-window layer history; refuse seedHistories when tape JSON exists. */
export function useHistoryTape(asset: string) {
  const loadHistoryFromApi = useMarketStore((s) => s.loadHistoryFromApi);
  const applyAsOf = useMarketStore((s) => s.applyAsOf);
  const clearHistories = useMarketStore((s) => s.clearHistories);
  const replayMode = useMarketStore((s) => s.replayMode);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  const historyLoaded = useMarketStore((s) => s.historyLoaded);
  const mounted = useRef(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const tryLoad = async (
        url: string,
        source: "api" | "static"
      ): Promise<boolean> => {
        const res = await fetch(url);
        if (!res.ok) return false;
        const body = await res.json();
        const layers = body.layers ?? body;
        if (!layers || typeof layers !== "object") return false;
        if (!cancelled) {
          loadHistoryFromApi(asset, layers, source);
          mounted.current = true;
        }
        return true;
      };

      try {
        if (
          await tryLoad(
            `${API_URL}/api/v1/history/${encodeURIComponent(asset)}`,
            "api"
          )
        ) {
          return;
        }
      } catch {
        /* fall through to static tape */
      }

      try {
        if (await tryLoad(historyJsonUrl(asset), "static")) {
          return;
        }
      } catch {
        /* empty state */
      }

      if (!cancelled) {
        clearHistories();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [asset, loadHistoryFromApi, clearHistories]);

  useEffect(() => {
    if (!historyLoaded || !replayMode || replayTimestamp == null) return;
    const iso = new Date(replayTimestamp * 1000).toISOString().slice(0, 10);
    applyAsOf(asset, iso);
  }, [asset, applyAsOf, historyLoaded, replayMode, replayTimestamp]);
}
