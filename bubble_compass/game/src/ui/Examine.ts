/** Examine templates only. Never invent LTV/CDS/PD or rift dates. */

import { EPISODES } from "../../../shared/episodes";
import { plainDate } from "../../../shared/plainDate";
import type { DeskHud } from "../systems/TapePlayer";
import type { DistrictDef, StoneDef } from "../world/TownLayout";

const BOOK_NAME: Record<string, string> = {
  SP500_TOTAL_RETURN: "Stocks",
  BBG_US_HIGH_YIELD_TOTAL_RETURN: "High yield",
  BBG_US_CORPORATE_TOTAL_RETURN: "Corporates",
  BBG_US_TREASURY_TOTAL_RETURN: "Treasuries",
  GOLD_TOTAL_RETURN: "Gold",
  US_CASH_RETURN: "Cash",
  CDX_HY_5Y_TOTAL_RETURN: "High-yield insurance",
  CDX_IG_5Y_TOTAL_RETURN: "Investment-grade insurance",
};

export function bookName(sleeveId: string): string {
  return BOOK_NAME[sleeveId] ?? "this book";
}

export function examineSundial(asOf: string): string {
  return `Stamp the sundial to score ${plainDate(asOf)}. The stamp records the weights you set on the books.`;
}

export function examineFlatDay(): string {
  return "The book's return was flat. The stamp still scored.";
}

export function examineStretchStone(hud: DeskHud): string {
  const stretch = Number.isFinite(hud.stretch) ? hud.stretch.toFixed(2) : "unavailable";
  const cv = Number.isFinite(hud.criticalValue)
    ? hud.criticalValue.toFixed(2)
    : "unavailable";
  const marked = hud.bubbleFlag
    ? "The stretch flag is on."
    : "The stretch flag is off.";
  return `Stretch is ${stretch}. The critical value is ${cv}. ${marked} Stretch opens the crash gate only when it is more than 0.5 above the critical value and the book loses more than 2 percent. Heat at 70 or more opens the gate on its own.`;
}

export function examineBoard(hud: DeskHud): string {
  const win = String(hud.crashWindow ?? "-");
  if (!win || win === "-" || win.toLowerCase().includes("unavail")) {
    return "No timing posted on the board.";
  }
  const [start, end] = win.split("..");
  if (!start || !end) return "No timing posted on the board.";
  return `The board posts a window from ${plainDate(start)} to ${plainDate(end)}.`;
}

export function examineBard(): string {
  return "The door is barred. The bard has no song today.";
}

export function examineNameShop(): string {
  return "The name-shop is shuttered. No names are for sale.";
}

/** Tavern dialect on the index move. No issuer names. */
export function examineDistrict(
  d: DistrictDef,
  weight: number,
  sleeveReturn: number
): string {
  const weightPct = `${Math.round(weight * 100)}`;
  const book = bookName(d.sleeveId);
  let mood = "This book has no print on this tip.";
  if (Number.isFinite(sleeveReturn)) {
    if (sleeveReturn > 0.005) mood = "The last print was up.";
    else if (sleeveReturn < -0.005) mood = "The last print was down.";
    else mood = "The last print was flat.";
  }
  return `${d.place}. Your weight in ${book} is ${weightPct} percent. ${mood} Stamp the sundial to score the day.`;
}

export function examineStone(s: StoneDef): string {
  const ep = EPISODES.find((e) => e.id === s.episodeId);
  const flavor = ep?.blurb ?? "A flood mark on the public history.";
  return `${s.title}. The stone remembers ${plainDate(s.date)}. ${flavor} Touch it and the book turns to that day.`;
}

export function examineBook(
  asOf: string,
  heat: number,
  stretch: number,
  cv: number,
  albumCount?: number,
  opts?: { sleeveId?: string; visitCount?: number }
): string {
  const album =
    typeof albumCount === "number" ? ` Album ${albumCount}.` : "";
  const visits =
    opts?.sleeveId && typeof opts.visitCount === "number"
      ? ` Visits to this book: ${opts.visitCount}.`
      : "";
  return `The book is dated ${plainDate(asOf)}. Heat is ${heat.toFixed(0)}. Stretch is ${stretch.toFixed(2)} against a critical value of ${cv.toFixed(2)}. Set the weights, then stamp the sundial to score this day.${album}${visits}`;
}

export function examineEmptySlot(): string {
  return "Nothing here to read.";
}

export function examineGate(reason: string): string {
  return `The gate opens. ${reason}.`;
}

export function examineGravestone(): string {
  return "The sack splits. The book that lost the most falls first.";
}
