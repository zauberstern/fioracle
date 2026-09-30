import { useCallback, useEffect, useRef } from "react";
import { useMarketStore } from "../store/marketStore";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

interface UseWebSocketOptions {
  asset: string;
  autoReconnect?: boolean;
  maxRetries?: number;
}

export function useWebSocket({
  asset,
  autoReconnect = true,
  maxRetries = 5,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const pingIntervalRef = useRef<number | null>(null);

  const setConnected = useMarketStore((s) => s.setConnected);
  const updateDLinear = useMarketStore((s) => s.updateDLinear);
  const updateBSADF = useMarketStore((s) => s.updateBSADF);
  const updateLPPLS = useMarketStore((s) => s.updateLPPLS);
  const updateSentiment = useMarketStore((s) => s.updateSentiment);
  const updateRegime = useMarketStore((s) => s.updateRegime);
  const onBubbleConfirmed = useMarketStore((s) => s.onBubbleConfirmed);
  const onCrashWindowEntered = useMarketStore((s) => s.onCrashWindowEntered);
  const onRegimeFlip = useMarketStore((s) => s.onRegimeFlip);

  const handleMessage = useCallback(
    (msg: Record<string, unknown>) => {
      if (msg.type === "pong") return;
      const assetId = String(msg.asset ?? asset);
      if (msg.type === "initial_state") {
        const state = (msg.state ?? {}) as Record<string, Record<string, unknown>>;
        if (state.dlinear) {
          updateDLinear(assetId, {
            trend: Number(state.dlinear.trend),
            residual: Number(state.dlinear.residual),
            residualZ: Number(state.dlinear.residual_z ?? state.dlinear.residualZ),
          });
        }
        if (state.bsadf) {
          updateBSADF(assetId, {
            bsadfStat: Number(state.bsadf.bsadf_stat ?? state.bsadf.bsadfStat),
            criticalValue: Number(state.bsadf.critical_value ?? state.bsadf.criticalValue),
            bubbleFlag: Boolean(state.bsadf.bubble_flag ?? state.bsadf.bubbleFlag),
          });
        }
        if (state.lppls) {
          const start = state.lppls.crash_window_start ?? state.lppls.crashWindowStart;
          const end = state.lppls.crash_window_end ?? state.lppls.crashWindowEnd;
          updateLPPLS(assetId, {
            lppConfidence: Number(state.lppls.lpp_confidence ?? state.lppls.lppConfidence),
            crashWindowStart: start ? new Date(String(start)) : null,
            crashWindowEnd: end ? new Date(String(end)) : null,
          });
        }
        if (state.sentiment) {
          updateSentiment(assetId, {
            sentimentVelocity: Number(
              state.sentiment.sentiment_velocity ?? state.sentiment.sentimentVelocity
            ),
            sentimentLevel: Number(
              state.sentiment.sentiment_level ?? state.sentiment.sentimentLevel
            ),
          });
        }
        if (state.regime) {
          updateRegime(assetId, {
            regimeState: String(state.regime.regime_state ?? state.regime.regimeState) as
              | "normal"
              | "boom"
              | "bust",
            regimeConfidence: Number(
              state.regime.regime_confidence ?? state.regime.regimeConfidence
            ),
            boomProbability: Number(
              state.regime.boom_probability ?? state.regime.boomProbability
            ),
            bustProbability: Number(
              state.regime.bust_probability ?? state.regime.bustProbability
            ),
          });
        }
        return;
      }
      if (msg.type === "state_delta") {
        if (msg.layer === "dlinear") {
          updateDLinear(assetId, {
            trend: Number(msg.trend),
            residual: Number(msg.residual),
            residualZ: Number(msg.residual_z),
          });
        } else if (msg.layer === "bsadf") {
          updateBSADF(assetId, {
            bsadfStat: Number(msg.bsadf_stat),
            criticalValue: Number(msg.critical_value),
            bubbleFlag: Boolean(msg.bubble_flag),
          });
        } else if (msg.layer === "lppls") {
          updateLPPLS(assetId, {
            lppConfidence: Number(msg.lpp_confidence),
            crashWindowStart: msg.crash_window_start
              ? new Date(String(msg.crash_window_start))
              : null,
            crashWindowEnd: msg.crash_window_end
              ? new Date(String(msg.crash_window_end))
              : null,
          });
        } else if (msg.layer === "sentiment") {
          updateSentiment(assetId, {
            sentimentVelocity: Number(msg.sentiment_velocity),
            sentimentLevel: Number(msg.sentiment_level),
          });
        } else if (msg.layer === "regime") {
          updateRegime(assetId, {
            regimeState: String(msg.regime_state) as "normal" | "boom" | "bust",
            regimeConfidence: Number(msg.regime_confidence),
            boomProbability: Number(msg.boom_probability),
            bustProbability: Number(msg.bust_probability),
          });
        }
        return;
      }
      if (msg.type === "regime_event") {
        if (msg.event === "bubble_confirmed") onBubbleConfirmed(assetId);
        if (msg.event === "crash_window_entered") onCrashWindowEntered(assetId);
        if (msg.event === "regime_flip") {
          onRegimeFlip(assetId, String(msg.from_state), String(msg.to_state));
        }
      }
    },
    [
      asset,
      onBubbleConfirmed,
      onCrashWindowEntered,
      onRegimeFlip,
      updateBSADF,
      updateDLinear,
      updateLPPLS,
      updateRegime,
      updateSentiment,
    ]
  );

  const connect = useCallback(() => {
    const url = `${WS_URL}/${asset}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      retriesRef.current = 0;
      pingIntervalRef.current = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 25000);
    };
    ws.onclose = () => {
      setConnected(false);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (autoReconnect && retriesRef.current < maxRetries) {
        const delay = Math.min(1000 * 2 ** retriesRef.current, 30000);
        retriesRef.current += 1;
        window.setTimeout(connect, delay);
      }
    };
    ws.onmessage = (event) => {
      try {
        handleMessage(JSON.parse(event.data));
      } catch {
        /* ignore malformed frames */
      }
    };
  }, [asset, autoReconnect, handleMessage, maxRetries, setConnected]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
    };
  }, [connect]);

  return {
    send: (data: unknown) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(data));
      }
    },
  };
}
