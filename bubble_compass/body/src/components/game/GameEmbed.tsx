import { useEffect, useRef, useState } from "react";
import { useMarketStore } from "../../store/marketStore";

/** Embed Stillmoor (As-Of Desk iframe title kept for Playwright). */
const GAME_URL =
  import.meta.env.VITE_GAME_URL ||
  (import.meta.env.DEV
    ? "http://localhost:5174/"
    : `${import.meta.env.BASE_URL || "/"}desk/`);

function gameOrigin(): string {
  try {
    return new URL(GAME_URL, window.location.href).origin;
  } catch {
    return window.location.origin;
  }
}

type GameToParent =
  | { type: "boot" }
  | { type: "ready" }
  | { type: "turnCommitted"; asOf: string; weights: Record<string, number>; score: number }
  | { type: "requestFocus" }
  | { type: "error"; message: string };

export function GameEmbed() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [needsFocus, setNeedsFocus] = useState(true);
  const [ready, setReady] = useState(false);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  const setReplayTimestamp = useMarketStore((s) => s.setReplayTimestamp);
  /** Skip echoing asOf back into the desk after a stamp (avoids rewind). */
  const skipEchoRef = useRef(false);
  /** Last asOf from turnCommitted (same-day stamp may not re-fire the effect). */
  const lastCommittedAsOfRef = useRef<string | null>(null);

  const post = (msg: Record<string, unknown>) => {
    const win = iframeRef.current?.contentWindow;
    if (!win) return;
    const target = gameOrigin();
    try {
      win.postMessage(msg, target);
    } catch {
      if (import.meta.env.DEV) {
        try {
          win.postMessage(msg, "*");
        } catch {
          /* ignore */
        }
      }
    }
  };

  useEffect(() => {
    const onMsg = (ev: MessageEvent) => {
      const data = ev.data as GameToParent;
      if (!data || typeof data !== "object" || !("type" in data)) return;
      const expected = gameOrigin();
      if (ev.origin !== expected && !import.meta.env.DEV) return;
      switch (data.type) {
        case "boot": {
          const ts = useMarketStore.getState().replayTimestamp;
          if (ts != null) {
            const iso = new Date(ts * 1000).toISOString().slice(0, 10);
            post({ type: "asOf", date: iso });
          }
          const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
          post({ type: "reducedMotion", on: mq.matches });
          break;
        }
        case "ready":
          setReady(true);
          setNeedsFocus(false);
          setLoadError(null);
          break;
        case "turnCommitted":
          if (data.asOf) {
            const s = data.asOf.slice(0, 10);
            // Store the desk ISO as given; do not re-snap onto one sleeve.
            const unix = Math.floor(
              Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) /
                1000
            );
            lastCommittedAsOfRef.current = s;
            skipEchoRef.current = true;
            setReplayTimestamp(unix);
            // Skip clears only in the echo effect (no microtask race).
          }
          break;
        case "requestFocus":
          setNeedsFocus(true);
          break;
        case "error":
          setLoadError(data.message);
          break;
        default:
          break;
      }
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, [setReplayTimestamp]);

  useEffect(() => {
    if (!ready || replayTimestamp == null) return;
    const d = new Date(replayTimestamp * 1000);
    const iso = d.toISOString().slice(0, 10);
    if (skipEchoRef.current) {
      skipEchoRef.current = false;
      return;
    }
    // Do not echo the date the desk just committed (same-day or advanced).
    if (lastCommittedAsOfRef.current === iso) return;
    post({ type: "asOf", date: iso });
  }, [replayTimestamp, ready]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const send = () => post({ type: "reducedMotion", on: mq.matches });
    send();
    mq.addEventListener?.("change", send);
    return () => mq.removeEventListener?.("change", send);
  }, [ready]);

  const focusIframe = () => {
    iframeRef.current?.focus();
    iframeRef.current?.contentWindow?.focus();
    setNeedsFocus(false);
    post({ type: "resume" });
  };

  return (
    <div className="game-embed">
      <div className="game-embed-banner">Stillmoor uses this same reading.</div>
      <div className="game-embed-frame-wrap">
        {needsFocus ? (
          <button
            type="button"
            className="game-embed-focus"
            onClick={focusIframe}
          >
            Click to wake the desk
          </button>
        ) : null}
        <iframe
          ref={iframeRef}
          title="As-Of Desk"
          src={GAME_URL}
          className="game-embed-frame"
          allow="autoplay"
          tabIndex={0}
          onLoad={() => setLoadError(null)}
          onError={() => setLoadError(`Failed to load ${GAME_URL}`)}
        />
      </div>
      {loadError ? (
        <p className="game-embed-help game-embed-error">
          {loadError}. Locally run{" "}
          <code>cd bubble_compass/game && npm run dev</code> if the frame is blank.
        </p>
      ) : null}
    </div>
  );
}
