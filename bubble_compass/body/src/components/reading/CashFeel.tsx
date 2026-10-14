import { useEffect, useMemo, useState } from "react";
import {
  dollarDelta,
  feelLine,
  gistTag,
  pieConic,
  rankBasket,
  type BookMove,
  type MixPie,
} from "../../narrator/cashFeel";
import type { StatusWord } from "../../narrator/heat";

const STORE = "fioracle-cash-feel-v1";
const CURRENCIES = ["USD", "CHF", "EUR", "GBP"] as const;

type Saved = { amount: number; currency: string };

function readSaved(): Saved {
  try {
    const raw = localStorage.getItem(STORE);
    if (!raw) return { amount: 100000, currency: "USD" };
    const parsed = JSON.parse(raw) as Saved;
    const amount = Number(parsed.amount);
    const currency = CURRENCIES.includes(parsed.currency as (typeof CURRENCIES)[number])
      ? parsed.currency
      : "USD";
    return {
      amount: Number.isFinite(amount) && amount > 0 ? amount : 100000,
      currency,
    };
  } catch {
    return { amount: 100000, currency: "USD" };
  }
}

function money(n: number): string {
  const abs = Math.abs(n);
  const body =
    abs >= 100
      ? abs.toLocaleString("en-US", { maximumFractionDigits: 0 })
      : abs.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return (n < 0 ? "-" : "+") + body;
}

function Pie({ pie, title }: { pie: MixPie; title: string }) {
  const tip = pie.slices.map((s) => `${s.group} ${s.pct.toFixed(0)}%`).join(", ");
  return (
    <li className="cash-feel-pie" title={tip || "No weights this mark"}>
      <span
        className="cash-feel-disc"
        style={{ background: pieConic(pie.slices) }}
        aria-hidden="true"
      />
      <div>
        <strong>{title}</strong>
        <span>
          {pie.delta != null ? money(pie.delta) : "n/a"}
          {pie.slices[0] ? ` · ${pie.slices[0].group} ${pie.slices[0].pct.toFixed(0)}%` : ""}
        </span>
      </div>
    </li>
  );
}

type Props = {
  date: string;
  heat: number;
  word: StatusWord | "Loading";
  moves: BookMove[];
  hotName: string | null;
  hotRet: number | null;
};

export function CashFeel({ date, heat, word, moves, hotName, hotRet }: Props) {
  const [amount, setAmount] = useState(100000);
  const [currency, setCurrency] = useState("USD");

  useEffect(() => {
    const saved = readSaved();
    setAmount(saved.amount);
    setCurrency(saved.currency);
  }, []);

  useEffect(() => {
    localStorage.setItem(STORE, JSON.stringify({ amount, currency }));
  }, [amount, currency]);

  const ranked = useMemo(() => rankBasket(moves, amount), [moves, amount]);
  const cashDelta = ranked.cash?.delta ?? 0;
  const bestDelta = ranked.best.delta ?? 0;
  const worstDelta = ranked.worst.delta ?? 0;
  const hotDelta = dollarDelta(amount, hotRet);
  const status: StatusWord = word === "Loading" ? "Quiet" : word;
  const ready =
    ranked.best.slices.length > 0 ||
    ranked.smooth.slices.length > 0 ||
    ranked.worst.slices.length > 0;
  const tag = ready
    ? gistTag({
        word: status,
        cashDelta,
        bestDelta,
        worstDelta,
        hotDelta,
      })
    : "loading";
  const line =
    ranked.cash && ready
      ? feelLine({
          amount,
          currency,
          date,
          cashName: ranked.cash.name,
          cashDelta,
          bestDelta,
          worstDelta,
          heat,
          word: status,
        })
      : "The tape for this date is still loading.";

  return (
    <aside className="cash-feel" aria-label="What this heat does to parked cash">
      <div className="cash-feel-head">
        <label>
          Parked
          <input
            type="number"
            min={1}
            step={1000}
            value={amount}
            aria-label="Cash pile"
            onChange={(event) => {
              const n = Number(event.target.value);
              if (Number.isFinite(n) && n > 0) setAmount(n);
            }}
          />
        </label>
        <label>
          Currency
          <select
            value={currency}
            aria-label="Currency"
            onChange={(event) => setCurrency(event.target.value)}
          >
            {CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <p className="cash-feel-tag">{tag}</p>
      </div>
      {ready ? (
        <ul className="cash-feel-pies">
          <Pie pie={ranked.best} title="Best mix" />
          <Pie pie={ranked.smooth} title="Smoothest" />
          <Pie pie={ranked.worst} title="Worst mix" />
          {ranked.cash ? (
            <li className="cash-feel-cash">
              <span>Your pile</span>
              <strong>
                {ranked.cash.name} {money(ranked.cash.delta)}
              </strong>
            </li>
          ) : null}
        </ul>
      ) : (
        <p className="cash-feel-wait">Waiting on the tape.</p>
      )}
      {hotName && hotDelta != null ? (
        <p className="cash-feel-hot">
          Hottest book {hotName} {money(hotDelta)}.
        </p>
      ) : null}
      <p className="cash-feel-line">{line}</p>
      <p className="cash-feel-note">
        USD total-return tape on the number you typed. No FX conversion.
      </p>
    </aside>
  );
}
