import { useRef } from "react";
import { plainDate } from "../../../../shared/plainDate";
import type { HeatParts } from "../../narrator/heat";

export type MatrixBook = {
  key: string;
  name: string;
  heat: number;
  word: "Quiet" | "Warming" | "Stretched";
  lines: string[];
  move: string;
  parts: HeatParts;
  cash?: boolean;
};

const PIECES: Array<[string, keyof HeatParts]> = [
  ["The distance above its path", "residual"],
  ["The fast-rise check", "bsadf"],
  ["A break date", "lppls"],
  ["News tone", "sentiment"],
];

function leadPiece(parts: HeatParts): string {
  let label = PIECES[0]![0];
  let best = parts[PIECES[0]![1]];
  for (const [name, key] of PIECES) {
    if (parts[key] > best) {
      best = parts[key];
      label = name;
    }
  }
  return `${label} is the largest part, at ${best.toFixed(1)}.`;
}

type Props = {
  books: MatrixBook[];
  date: string;
  activeId: string | null;
  onActive: (id: string | null) => void;
  onPick: (id: string) => void;
};

const COLS = 4;

export function BookMatrix({ books, date, activeId, onActive, onPick }: Props) {
  const grid = useRef<HTMLDivElement>(null);
  const active = books.find((b) => b.key === activeId) ?? null;

  const move = (from: number, key: string) => {
    let next = from;
    if (key === "ArrowRight") next = Math.min(books.length - 1, from + 1);
    else if (key === "ArrowLeft") next = Math.max(0, from - 1);
    else if (key === "ArrowDown") next = Math.min(books.length - 1, from + COLS);
    else if (key === "ArrowUp") next = Math.max(0, from - COLS);
    else return;
    const id = books[next]?.key;
    if (!id) return;
    onActive(id);
    const el = grid.current?.querySelector<HTMLButtonElement>(
      `[data-book="${CSS.escape(id)}"]`
    );
    el?.focus();
  };

  return (
    <div
      className="week-matrix"
      onMouseLeave={(event) => {
        const next = event.relatedTarget;
        if (next instanceof Node && event.currentTarget.contains(next)) return;
        if (event.currentTarget.contains(document.activeElement)) return;
        onActive(null);
      }}
      onBlur={(event) => {
        const next = event.relatedTarget;
        if (next instanceof Node && event.currentTarget.contains(next)) return;
        onActive(null);
      }}
    >
      <div
        ref={grid}
        className="book-matrix"
        role="grid"
        aria-label="Heat of each book on this date"
      >
        {books.map((book, index) => {
          const on = book.key === activeId;
          return (
            <button
              key={book.key}
              type="button"
              role="gridcell"
              data-book={book.key}
              tabIndex={on || (activeId == null && index === 0) ? 0 : -1}
              className={on ? `mx-cell mx-${book.word} mx-on` : `mx-cell mx-${book.word}`}
              aria-label={`${book.name}, ${book.word}, ${book.heat.toFixed(1)}`}
              onMouseEnter={() => onActive(book.key)}
              onFocus={() => onActive(book.key)}
              onClick={() => onPick(book.key)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  onActive(null);
                  return;
                }
                if (
                  event.key === "ArrowRight" ||
                  event.key === "ArrowLeft" ||
                  event.key === "ArrowDown" ||
                  event.key === "ArrowUp"
                ) {
                  event.preventDefault();
                  move(index, event.key);
                }
              }}
            >
              <span className="mx-name">{book.name}</span>
              <span className="mx-num">{book.cash ? "0.0" : book.heat.toFixed(1)}</span>
            </button>
          );
        })}
      </div>
      {active ? (
        <div className="mx-panel" id="book-cell-detail">
          <p className="mx-panel-title">
            {active.name} on {date ? plainDate(date) : "this date"} is {active.word}{" "}
            at {active.cash ? "0.0" : active.heat.toFixed(1)}.
          </p>
          {active.move ? <p>{active.move}</p> : null}
          <p>{leadPiece(active.parts)}</p>
          <details className="mx-why">
            <summary>Why</summary>
            {active.lines.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </details>
        </div>
      ) : (
        <p className="mx-hint">Point at a cell to read that book on this date.</p>
      )}
    </div>
  );
}
