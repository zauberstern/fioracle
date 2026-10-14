import { useEffect, useMemo, useRef, useState } from "react";
import { BOOKS, bookName } from "../../../../shared/books";
import { EPISODES } from "../../copy/episodes";
import { playChangeSentence, readBook } from "../../narrator/scoreCopy";
import { useMarketStore } from "../../store/marketStore";
import { plainDate } from "../../../../shared/plainDate";
import { StatusMark } from "./StatusMark";

type Props = {
  onBack: () => void;
};

type LayerBundle = Record<string, Array<Record<string, unknown>>>;

const HISTORY_BASE =
  import.meta.env.VITE_HISTORY_BASE ||
  `${import.meta.env.BASE_URL || "/"}data/`;

function historyUrl(asset: string): string {
  const base = HISTORY_BASE.endsWith("/") ? HISTORY_BASE : `${HISTORY_BASE}/`;
  return `${base}history/${encodeURIComponent(asset)}.json`;
}

function isoToUnix(iso: string): number {
  return Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / 1000;
}

function spineOf(layers: LayerBundle | undefined): string[] {
  const rows = layers?.dlinear ?? [];
  const unique = new Set(
    rows
      .map((r) => String(r.as_of ?? "").slice(0, 10))
      .filter((d) => d.length >= 10)
  );
  return [...unique].sort();
}

export function ThenView({ onBack }: Props) {
  const setReplayTimestamp = useMarketStore((s) => s.setReplayTimestamp);
  const setCurrentAsset = useMarketStore((s) => s.setCurrentAsset);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  const currentAsset = useMarketStore((s) => s.currentAsset);
  const rangeRef = useRef<HTMLInputElement>(null);
  const [cache, setCache] = useState<Map<string, LayerBundle>>(() => new Map());

  const book = BOOKS.find((b) => b.id === currentAsset) ?? {
    id: currentAsset,
    name: bookName(currentAsset),
    short: bookName(currentAsset),
    plain: bookName(currentAsset),
    mark: "",
    group: "",
    hint: "",
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const next = new Map<string, LayerBundle>();
      for (const item of BOOKS) {
        try {
          const res = await fetch(historyUrl(item.id));
          if (!res.ok) continue;
          const body = await res.json();
          const layers = (body.layers ?? body) as LayerBundle;
          if (layers) next.set(item.id, layers);
        } catch {
          /* skip a missing book */
        }
      }
      if (!cancelled) setCache(next);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const spine = useMemo(() => {
    const preferred = spineOf(cache.get("SP500_TOTAL_RETURN"));
    if (preferred.length) return preferred;
    let best: string[] = [];
    for (const layers of cache.values()) {
      const dates = spineOf(layers);
      if (dates.length > best.length) best = dates;
    }
    return best;
  }, [cache]);

  const pinIso =
    replayTimestamp != null
      ? new Date(replayTimestamp * 1000).toISOString().slice(0, 10)
      : spine[spine.length - 1] ?? "";

  const sliderIndex = useMemo(() => {
    if (!spine.length) return 0;
    const exact = spine.indexOf(pinIso);
    if (exact >= 0) return exact;
    let best = 0;
    for (let i = 0; i < spine.length; i++) {
      if (spine[i]! <= pinIso) best = i;
    }
    return best;
  }, [spine, pinIso]);

  const current = spine[sliderIndex] ?? "";
  const prevDate = sliderIndex > 0 ? spine[sliderIndex - 1]! : "";
  const layers = cache.get(book.id);
  const reading = current && layers ? readBook(book, layers, current) : null;
  const prevReading =
    prevDate && layers ? readBook(book, layers, prevDate) : null;

  const pin = (iso: string) => setReplayTimestamp(isoToUnix(iso));

  const step = (delta: number) => {
    const next = spine[sliderIndex + delta];
    if (next) pin(next);
  };

  const hop = (index: number) => {
    const ep = EPISODES[index];
    if (!ep) return;
    const hit = [...spine].reverse().find((d) => d <= ep.date);
    if (hit) pin(hit);
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target != null &&
        (target.tagName === "SELECT" ||
          target.tagName === "TEXTAREA" ||
          (target.tagName === "INPUT" && target.id !== "play-range"));
      if (typing) return;
      if (event.key >= "1" && event.key <= "5") {
        event.preventDefault();
        hop(Number(event.key) - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [spine]);

  const chooseBook = (id: string) => setCurrentAsset(id);
  const caption =
    EPISODES.find((ep) => {
      const hit = [...spine].reverse().find((d) => d <= ep.date);
      return hit === current;
    })?.title ?? (current ? plainDate(current) : "Loading");
  const sentence = reading
    ? playChangeSentence({
        name: book.name,
        cash: book.cash,
        now: reading,
        prev: prevReading,
        nowDate: current,
        prevDate,
      })
    : "";

  return (
    <article className="reading-page play-page">
      <header className="play-head">
        <h1>History</h1>
        <p className="play-now">{current ? plainDate(current) : "Loading"}</p>
      </header>
      <p className="reading-lede">
        Drag the line. A mark's name shows when you point at it. Keys 1 to 5
        hop to the five dates. The number is how {book.name} read on that row.
      </p>
      <p className="play-caption" id="history-caption">
        {caption}
      </p>

      <section className="play-rail" aria-label="History">
        <div className="play-track-wrap">
          <div
            className="play-track-fill"
            style={{
              width: spine.length > 1 ? `${(sliderIndex / (spine.length - 1)) * 100}%` : "0%",
            }}
          />
          <input
            ref={rangeRef}
            id="play-range"
            className="play-range"
            type="range"
            min={0}
            max={Math.max(0, spine.length - 1)}
            value={sliderIndex}
            disabled={spine.length === 0}
            aria-labelledby="history-caption"
            aria-valuetext={caption}
            onChange={(e) => {
              const d = spine[Number(e.target.value)];
              if (d) pin(d);
            }}
          />
          {EPISODES.map((ep, index) => {
            const hit = [...spine].reverse().find((d) => d <= ep.date);
            if (!hit) return null;
            const at = spine.indexOf(hit);
            const left = spine.length > 1 ? (at / (spine.length - 1)) * 100 : 0;
            const on = hit === current;
            return (
              <button
                key={ep.id}
                type="button"
                className={
                  ep.id === "gfc"
                    ? on
                      ? "play-stop play-stop-below play-stop-on"
                      : "play-stop play-stop-below"
                    : on
                      ? "play-stop play-stop-on"
                      : "play-stop"
                }
                style={{ left: `${left}%` }}
                aria-label={ep.title}
                aria-pressed={on}
                onClick={() => pin(hit)}
              >
                <span className="play-tick" />
                <span className="play-tip">{ep.title}</span>
              </button>
            );
          })}
        </div>
        <div className="play-steps">
          <button type="button" onClick={() => step(-1)} disabled={sliderIndex <= 0}>
            Earlier row
          </button>
          <button
            type="button"
            onClick={() => step(1)}
            disabled={sliderIndex >= spine.length - 1}
          >
            Later row
          </button>
        </div>
      </section>

      <label className="closer-book">
        Book
        <select value={book.id} onChange={(e) => chooseBook(e.target.value)}>
          {BOOKS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.mark} {item.plain}
            </option>
          ))}
        </select>
      </label>

      {spine.length === 0 ? (
        <p className="reading-lede">The series are still loading.</p>
      ) : reading ? (
        <section className="play-result" aria-live="polite">
          <div className="play-score">
            <p className="play-heat">
              {book.cash ? "0.0" : reading.heat.toFixed(1)}
            </p>
            <div className="play-face">
              <StatusMark word={reading.word} />
              <span className={reading.word === "Stretched" ? "play-word play-word-hot" : "play-word"}>
                {reading.word}
              </span>
            </div>
          </div>
          <p className="play-sentence">{sentence}</p>
          <details className="play-why">
            <summary>Why</summary>
            {reading.lines.map((line) => (
              <p key={line}>{line}</p>
            ))}
            {reading.move ? <p>{reading.move}</p> : null}
            {reading.dailyReturn === 0 && current === "2026-01-12" ? (
              <p>On this row the return is 0.</p>
            ) : null}
          </details>
          <button type="button" className="then-open-week" onClick={onBack}>
            Open the week at this date
          </button>
        </section>
      ) : (
        <p className="reading-lede">This book's history is still loading.</p>
      )}
    </article>
  );
}
