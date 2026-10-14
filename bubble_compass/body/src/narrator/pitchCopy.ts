export type PitchBlock = { kind: "p" | "eq" | "h"; text: string };

export const PITCH_BLOCKS: readonly PitchBlock[] = [
  { kind: "p", text: "Quiet: under 40." },
  { kind: "p", text: "Warming: from 40." },
  { kind: "p", text: "Stretched: from 70." },
  {
    kind: "p",
    text: "The number adds distance above the book's path and a fast-rise check, and it stops at 100.",
  },
  { kind: "h", text: "The pin" },
  {
    kind: "p",
    text: "You pin a date. Meridian keeps the latest row dated on or before that date. A later row is not used to explain an earlier one. Cash is held at 0 and left out of the ranking.",
  },
  {
    kind: "p",
    text: "Four parts can enter the sum, and the sum stops at 100. On this history two of those parts add 0, so the number on the page is the path distance plus the fast-rise check. The history has 23 books. A new row arrives about every 21 business days. The week page shows the same cuts in a shorter line. This page writes the weights.",
  },
  { kind: "h", text: "How the number is made" },
  {
    kind: "p",
    text: "The path is the one drawn by DLinear, Zeng, Chen, Zhang and Xu (2022). z is how many steps the book sits above that path. Only a positive distance counts. Each step adds 12 points. This part stops at 40. A book below the path adds 0 from this part.",
  },
  { kind: "eq", text: "\\mathrm{path} = \\min(40, \\max(0, z) \\times 12)" },
  {
    kind: "p",
    text: "The fast-rise check is the Phillips, Shi and Yu (2015) screen. s is the fast-rise reading. c is the ordinary line on that row. The printed line is 1.49 unless the row carries another critical value.",
  },
  {
    kind: "p",
    text: "When the check is on, this part starts at 25 and adds 8 points for each unit past that line. A reading that is not past the line still scores 25. A reading of 2.49 scores 33. This part has no cap of its own. The sum of all four parts is what stops at 100.",
  },
  { kind: "eq", text: "\\mathrm{rise} = 25 + \\max(0, s - c) \\times 8" },
  {
    kind: "p",
    text: "When the check is off, this part is five times the reading, and it does not start at 25. A reading below zero adds 0. A reading of 3 scores 15. A reading of 8 scores 40. A reading of 14 scores 70, before the other parts are added and before the sum stops at 100. The check is on or off. The page uses one of those two lines, not both.",
  },
  { kind: "eq", text: "\\mathrm{rise} = \\max(0, s) \\times 5" },
  {
    kind: "p",
    text: "A break date is the log-periodic fit. It can add up to 30 points when a fit exists. News tone can add up to 15 points when headlines exist. On this history both layers are unavailable, so each adds 0. The four parts are added, and anything past 100 is cut off.",
  },
  {
    kind: "eq",
    text: "\\mathrm{break} = 0 \\quad \\text{or} \\quad \\mathrm{confidence} \\times 30",
  },
  {
    kind: "eq",
    text: "\\mathrm{tone} = 0 \\quad \\text{or} \\quad |\\mathrm{velocity}| \\times 15",
  },
  {
    kind: "eq",
    text: "\\mathrm{heat} = \\min(100, \\max(0, \\mathrm{path} + \\mathrm{rise} + \\mathrm{break} + \\mathrm{tone}))",
  },
  {
    kind: "p",
    text: "Take a book that sits 2 steps above its path, with the check off and a reading of 3. The path term is 24. The fast-rise term is 15. Break and tone add 0. The sum is 39, which is Quiet. The same steps with the check on and a reading of 2.49 give a fast-rise term of 33, so the sum is 57, which is Warming. Neither pair is a row from this history. Each pair is the weights applied to a chosen z and s.",
  },
  {
    kind: "p",
    text: "Cash does not use those weights. Its path term, fast-rise term, break term, and tone term are set to 0, and its heat is 0. It remains on the page so the other 22 books can be ranked without it.",
  },
  { kind: "h", text: "What this history shows" },
  {
    kind: "p",
    text: "A break date and news tone stay in the formula and add 0 on every row. Two books with the same path distance and the same fast-rise reading receive the same heat. Headlines and a dated break cannot separate them here. The zero is the same on the first row and on the last row.",
  },
  {
    kind: "p",
    text: "The recorded state is normal on every row, including 2020. Boom and bust probabilities can still move. A row may carry a bust probability and remain labelled normal. That word is not one of the four parts, so a change in the word cannot move the heat. On this history the word does not change.",
  },
  {
    kind: "p",
    text: "The oil book, the US inflation-linked book, and the Swiss franc book are total returns. Pump prices, consumer prices, and spot exchange rates are separate series and are not in this history.",
  },
  {
    kind: "p",
    text: "Stillmoor is the same history, played as a desk. Set a weight on each book and stamp the sundial. A stamp scores that day when every book and the bench have a print. A missing print does not score.",
  },
  { kind: "h", text: "Limits" },
  {
    kind: "p",
    text: "These figures describe the public marks for the date you pinned. They are not a forecast or a recommendation.",
  },
  {
    kind: "p",
    text: "A cost or a constraint would enter where Grinold and Kahn (2020) and Noguer (2025) place it.",
  },
  {
    kind: "p",
    text: "On this history the heat of a book other than cash is the path term plus the fast-rise term. The break-date term and the news-tone term stay in the sum and add 0. A book below its path takes nothing from the path term, so only the fast-rise check can move its heat.",
  },
];

export function pitchPlain(): string {
  return PITCH_BLOCKS.map((b) => b.text).join(" ");
}
