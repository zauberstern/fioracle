import { useEffect, useMemo, useState } from "react";
import { BOOKS } from "../../../../shared/books";
import { plainDate } from "../../../../shared/plainDate";
import { EPISODES } from "../../copy/episodes";
import { useMarketStore } from "../../store/marketStore";
import { rowOnOrBefore, statusWord } from "../../narrator/heat";
import { heroFromCards } from "../../narrator/readingCopy";
import {
  buildSleeveTip,
  type NarratorContext,
  type NarratorQuestionId,
} from "../../narrator/narrator";
import {
  MACHINERY,
  bookMarkSentence,
  heatClose,
  padSentence,
  readBook,
  sharedMarkSentences,
  spineSentence,
  type HeatParts,
} from "../../narrator/scoreCopy";
import { BookMatrix } from "./BookMatrix";
import { HeatField, type HeatCol } from "./HeatField";
import { StatusMark } from "./StatusMark";
import { TalkRail } from "./TalkRail";

const HISTORY_BASE =
  import.meta.env.VITE_HISTORY_BASE ||
  `${import.meta.env.BASE_URL || "/"}data/`;

const MARK_IDS = [
  "WTI_TOTAL_RETURN",
  "US_TIPS_0_5_TOTAL_RETURN",
  "CHF_TOTAL_RETURN",
] as const;

type CardState = {
  key: string;
  name: string;
  heat: number;
  word: ReturnType<typeof statusWord>;
  lines: string[];
  move: string;
  flag: boolean;
  parts: HeatParts;
  focusId: string;
  sleeveIds: string[];
  cash?: boolean;
  dailyReturn: number | null;
};

type LayerBundle = Record<string, Array<Record<string, unknown>>>;

function historyUrl(asset: string): string {
  const base = HISTORY_BASE.endsWith("/") ? HISTORY_BASE : `${HISTORY_BASE}/`;
  return `${base}history/${encodeURIComponent(asset)}.json`;
}

async function fetchLayers(asset: string): Promise<LayerBundle | null> {
  try {
    const res = await fetch(historyUrl(asset));
    if (!res.ok) return null;
    const body = await res.json();
    return (body.layers ?? body) as LayerBundle;
  } catch {
    return null;
  }
}

function isoToUnix(iso: string): number {
  return Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / 1000;
}

function spineDates(layers: LayerBundle | undefined): string[] {
  const rows = layers?.dlinear ?? [];
  const unique = new Set(
    rows
      .map((r) => String(r.as_of ?? "").slice(0, 10))
      .filter((d) => d.length >= 10)
  );
  return [...unique].sort();
}

function cardsFromLayers(
  byId: Map<string, LayerBundle>,
  asOf: string | undefined
): { tips: ReturnType<typeof buildSleeveTip>[]; cards: CardState[] } {
  const tips: ReturnType<typeof buildSleeveTip>[] = [];
  for (const [id, layers] of byId) {
    tips.push(buildSleeveTip(id, layers, asOf));
  }
  const cards: CardState[] = BOOKS.map((book) => {
    const reading = readBook(book, byId.get(book.id), asOf);
    return {
      key: book.id,
      name: book.name,
      heat: reading.heat,
      word: reading.word,
      lines: reading.lines,
      move: reading.move,
      flag: reading.flag,
      parts: reading.parts,
      focusId: book.id,
      sleeveIds: [book.id],
      cash: book.cash,
      dailyReturn: reading.dailyReturn,
    };
  });
  return { tips, cards };
}

function groupLine(cards: CardState[]): string {
  const groups = cards.filter((c) => !c.cash);
  const stretched = groups.filter((c) => c.word === "Stretched").length;
  const warming = groups.filter((c) => c.word === "Warming").length;
  const n = groups.length;
  if (n === 0) return "";
  if (stretched > 0) {
    return stretched === 1
      ? `1 of ${n} books is stretched.`
      : `${stretched} of ${n} books are stretched.`;
  }
  if (warming > 0) {
    return warming === 1
      ? `1 of ${n} books is warming.`
      : `${warming} of ${n} books are warming.`;
  }
  return `All ${n} books are under 40.`;
}

function finiteField(
  row: Record<string, unknown> | null,
  key: string
): number | null {
  if (!row || row[key] == null) return null;
  const n = Number(row[key]);
  return Number.isFinite(n) ? n : null;
}

export function WeeklyReading() {
  const rawLayers = useMarketStore((s) => s.rawLayers);
  const historySource = useMarketStore((s) => s.historySource);
  const scoreHistory = useMarketStore((s) => s.scoreHistory);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  const setReplayTimestamp = useMarketStore((s) => s.setReplayTimestamp);
  const currentAsset = useMarketStore((s) => s.currentAsset);
  const setCurrentAsset = useMarketStore((s) => s.setCurrentAsset);
  const regime = useMarketStore((s) => s.getAssetState(currentAsset).regime);

  const [talkOpen, setTalkOpen] = useState(false);
  const [activeQ, setActiveQ] = useState<NarratorQuestionId | null>(null);
  const [crowd, setCrowd] = useState<CardState[]>([]);
  const [sleeveTips, setSleeveTips] = useState<
    ReturnType<typeof buildSleeveTip>[]
  >([]);
  const [layerCache, setLayerCache] = useState<Map<string, LayerBundle>>(
    () => new Map()
  );
  const [hoverId, setHoverId] = useState<string | null>(null);

  const asOf = useMemo(() => {
    if (replayTimestamp != null) {
      return new Date(replayTimestamp * 1000).toISOString().slice(0, 10);
    }
    const rows = rawLayers.dlinear ?? [];
    return String(rows[rows.length - 1]?.as_of ?? "").slice(0, 10);
  }, [rawLayers, replayTimestamp]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ids = BOOKS.map((b) => b.id);
      const next = new Map<string, LayerBundle>();
      for (const id of ids) {
        const layers = await fetchLayers(id);
        if (layers) next.set(id, layers);
      }
      if (cancelled) return;
      setLayerCache(next);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!layerCache.size) return;
    const pin = asOf || undefined;
    const { tips, cards } = cardsFromLayers(layerCache, pin);
    setSleeveTips(tips);
    setCrowd(cards);
  }, [asOf, layerCache]);

  const pin = asOf || undefined;
  const creditRows = rawLayers.credit_trajectory ?? [];
  const creditRow = pin
    ? rowOnOrBefore(creditRows, pin)
    : creditRows.length
      ? creditRows[creditRows.length - 1]!
      : null;

  const narratorCtx: NarratorContext = {
    sleeves:
      sleeveTips.length > 0
        ? sleeveTips
        : [buildSleeveTip(currentAsset, rawLayers, pin)],
    asOf: asOf || "unknown",
    selectedId: currentAsset,
    regimeState: regime.regimeState,
    credit: {
      hy_oas_level_bps:
        creditRow?.hy_oas_level_bps != null
          ? Number(creditRow.hy_oas_level_bps)
          : undefined,
      hy_oas_change_20d_bps:
        creditRow?.hy_oas_change_20d_bps != null
          ? Number(creditRow.hy_oas_change_20d_bps)
          : undefined,
      vix: creditRow?.vix != null ? Number(creditRow.vix) : undefined,
    },
    strideDays: 21,
    rowCount: scoreHistory.length,
    historySource,
  };

  const hero = heroFromCards(crowd);
  const heat = hero.heat;
  const word = hero.word;
  const oneLine = hero.sentence;

  const tipAgeDays = (() => {
    if (!asOf) return 0;
    const tip = Date.parse(`${asOf}T00:00:00Z`);
    if (!Number.isFinite(tip)) return 0;
    return Math.floor((Date.now() - tip) / 86400000);
  })();

  const spine = useMemo(() => {
    const stocks = layerCache.get("SP500_TOTAL_RETURN");
    const fromStocks = spineDates(stocks);
    if (fromStocks.length) return fromStocks;
    let best: string[] = [];
    for (const layers of layerCache.values()) {
      const dates = spineDates(layers);
      if (dates.length > best.length) best = dates;
    }
    return best;
  }, [layerCache]);

  const sliderIndex = useMemo(() => {
    if (!spine.length) return 0;
    if (!asOf) return spine.length - 1;
    let best = 0;
    for (let i = 0; i < spine.length; i++) {
      if (spine[i]! <= asOf) best = i;
    }
    return best;
  }, [spine, asOf]);

  const heatCols = useMemo<HeatCol[]>(() => {
    if (!spine.length) return [];
    return BOOKS.flatMap((book) => {
      const layers = layerCache.get(book.id);
      if (!layers) return [];
      return [
        {
          id: book.id,
          name: book.name,
          values: spine.map((date) => readBook(book, layers, date).heat),
        },
      ];
    });
  }, [layerCache, spine]);

  const refLayers =
    layerCache.get("SP500_TOTAL_RETURN") ??
    layerCache.values().next().value;
  const sharedRow = (() => {
    if (!refLayers || !pin) return null;
    const credit = rowOnOrBefore(refLayers.credit_trajectory, pin);
    const macro = rowOnOrBefore(refLayers.macro_debt, pin);
    return { credit, macro };
  })();
  const sharedLines =
    sharedRow && pin
      ? sharedMarkSentences({
          asOf: pin,
          hyBps: finiteField(sharedRow.credit, "hy_oas_level_bps"),
          hyChange: finiteField(sharedRow.credit, "hy_oas_change_20d_bps"),
          vix: finiteField(sharedRow.credit, "vix"),
          debt: finiteField(sharedRow.macro, "debt_to_gdp"),
          gap: finiteField(sharedRow.macro, "gap"),
          breach:
            sharedRow.macro?.threshold_breach == null
              ? null
              : Boolean(sharedRow.macro.threshold_breach),
        })
      : [];
  const spineLine =
    layerCache.size > 0 && spine.length > 1
      ? spineSentence(
          layerCache.size,
          spine.length,
          spine[0]!,
          spine[spine.length - 1]!
        )
      : "";
  const padLine = padSentence(crowd.map((c) => c.dailyReturn));
  const leader =
    crowd
      .filter((c) => !c.cash)
      .reduce<(typeof crowd)[number] | null>(
        (best, card) => (!best || card.heat > best.heat ? card : best),
        null
      ) ?? null;
  const shown = crowd.find((c) => c.key === hoverId) ?? leader;
  const ordered = BOOKS.flatMap((book) => {
    const card = crowd.find((c) => c.key === book.id);
    return card ? [card] : [];
  });
  const dateLabel = asOf ? plainDate(asOf) : "Date still loading.";

  return (
    <div className="weekly-reading">
      <section className="weekly-hero" aria-live="polite">
        <div className="weekly-mast">
          <div className="weekly-status-row">
            <StatusMark word={word === "Loading" ? "Quiet" : word} />
            <h1
              className={
                word === "Stretched"
                  ? "weekly-status-word weekly-status-warn"
                  : "weekly-status-word"
              }
            >
              {word}
            </h1>
          </div>
          <p className="weekly-heat">
            <span className="weekly-heat-label">Heat</span>
            <span className="weekly-heat-num">{heat}</span>
          </p>
        </div>
        <p className="weekly-sentence">{oneLine}</p>
        {crowd.length > 0 ? (
          <p className="weekly-sentence">{groupLine(crowd)}</p>
        ) : null}
        <p className={tipAgeDays > 8 ? "weekly-asof weekly-asof-stale" : "weekly-asof"}>
          {dateLabel}
        </p>
        <button
          type="button"
          className="weekly-means"
          onClick={() => setTalkOpen(true)}
        >
          Ask the reading
        </button>
      </section>

      <section className="week-stage" aria-label="Books across the history">
        <div>
          <HeatField
            dates={spine}
            cols={heatCols}
            index={sliderIndex}
            activeId={hoverId}
          />
          <p className="week-field-note">
            {asOf
              ? `Each line is one book. The marker sits on ${dateLabel}.`
              : "Each line is one book."}
          </p>
        </div>
        <BookMatrix
          books={ordered}
          date={asOf}
          activeId={hoverId}
          onActive={setHoverId}
          onPick={setCurrentAsset}
        />
      </section>

      <section className="week-scrub" aria-label="Date">
        <label htmlFor="week-date">{dateLabel}</label>
        <input
          id="week-date"
          type="range"
          min={0}
          max={Math.max(0, spine.length - 1)}
          value={sliderIndex}
          disabled={spine.length === 0}
          aria-valuemin={0}
          aria-valuemax={Math.max(0, spine.length - 1)}
          aria-valuenow={sliderIndex}
          aria-valuetext={dateLabel}
          onChange={(e) => {
            const d = spine[Number(e.target.value)];
            if (d) setReplayTimestamp(isoToUnix(d));
          }}
        />
        <p className="week-jump-help">Choose a date and the slider moves to it.</p>
        <div className="week-jumps">
          {EPISODES.map((ep) => {
            const hit = [...spine].reverse().find((d) => d <= ep.date);
            const selected = Boolean(hit) && spine[sliderIndex] === hit;
            return (
              <button
                key={ep.id}
                type="button"
                className="week-jump"
                disabled={!hit}
                aria-pressed={selected}
                onClick={() => {
                  if (hit) setReplayTimestamp(isoToUnix(hit));
                }}
              >
                <span className="week-jump-date">
                  {spine.length === 0
                    ? "Loading"
                    : hit
                      ? plainDate(hit)
                      : "Not on this history"}
                </span>
                <span className="week-jump-name">{ep.title}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="week-prose">
        {spineLine ? <p>{spineLine}</p> : null}
        {MACHINERY.map((paragraph) => (
          <p key={paragraph}>{paragraph}</p>
        ))}
        {padLine ? <p>{padLine}</p> : null}
      </section>

      {sharedLines.length > 0 || crowd.length > 0 ? (
        <section className="week-marks" aria-label="Shared marks">
          <h2>On this date</h2>
          <p>
            The oil book, the US inflation-linked book, and the Swiss franc
            book are total returns. Pump prices, consumer prices, and spot
            exchange rates are separate series and are not in this history.
          </p>
          {sharedLines.map((line) => (
            <p key={line}>{line}</p>
          ))}
          {MARK_IDS.map((id) => {
            const card = crowd.find((c) => c.key === id);
            if (!card || card.cash) return null;
            return (
              <p key={id}>
                {bookMarkSentence(card.name, card.parts, card.flag)}
              </p>
            );
          })}
        </section>
      ) : null}

      {shown ? (
        <section className="week-close" aria-live="polite">
          <h2>
            {shown.name} on {dateLabel}
          </h2>
          {shown.move ? <p>{shown.move}</p> : null}
          {shown.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
          <p>{heatClose(shown.name, shown.parts, shown.cash)}</p>
        </section>
      ) : (
        <p className="weekly-meta">The book figures are still loading.</p>
      )}

      <p className="weekly-disclaimer">
        These figures describe the public marks for this date. They are not a
        forecast or a recommendation.
      </p>

      <TalkRail
        open={talkOpen}
        onClose={() => setTalkOpen(false)}
        ctx={narratorCtx}
        activeId={activeQ}
        onAsk={setActiveQ}
      />
    </div>
  );
}
