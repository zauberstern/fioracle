/** Weekly hero copy from crowd cards. Hero heat is max non-cash card heat. */

import { statusWord, type StatusWord } from "./heat";

export type HeroCard = {
  name: string;
  heat: number;
  cash?: boolean;
  lines?: string[];
};

export type HeroReading = {
  heat: number;
  word: StatusWord | "Loading";
  leaderName: string | null;
  sentence: string;
};

export function heroFromCards(cards: HeroCard[]): HeroReading {
  // Empty crowd is not Quiet: histories are still loading.
  if (cards.length === 0) {
    return {
      heat: 0,
      word: "Loading",
      leaderName: null,
      sentence: "The public marks are still coming in.",
    };
  }
  const nonCash = cards.filter((c) => !c.cash);
  // Status word uses the same unrounded max the hottest card uses.
  const rawHeat =
    nonCash.length === 0 ? 0 : Math.max(...nonCash.map((c) => c.heat));
  const heat = Math.round(rawHeat);
  const word = statusWord(rawHeat);
  const leader =
    nonCash.length === 0
      ? null
      : [...nonCash].sort((a, b) => b.heat - a.heat)[0]!;
  const leaderName = leader && leader.heat >= 40 ? leader.name : null;
  return {
    heat,
    word,
    leaderName,
    sentence: sentenceFor(word, heat, leaderName, leader?.lines),
  };
}

export function sentenceFor(
  word: StatusWord,
  heat: number,
  leaderName: string | null,
  lines?: string[]
): string {
  const drivers = (lines ?? []).slice(0, 2).join(" ");
  if (word === "Quiet") {
    return drivers
      ? `The public marks are quiet. Heat is ${Math.round(heat)}. ${drivers}`
      : "The public marks are quiet.";
  }
  if (word === "Stretched") {
    const lead = leaderName
      ? `${leaderName} leads. Heat is ${Math.round(heat)}.`
      : `The public marks are stretched. Heat is ${Math.round(heat)}.`;
    return drivers ? `${lead} ${drivers}` : lead;
  }
  if (leaderName) {
    const lead = `${leaderName} leads. Heat is ${Math.round(heat)}.`;
    return drivers ? `${lead} ${drivers}` : lead;
  }
  return `Heat is ${Math.round(heat)}. Crash timing is not estimated on this date.`;
}
