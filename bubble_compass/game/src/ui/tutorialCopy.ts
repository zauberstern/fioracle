/** First-visit Stillmoor rules. Plain facts; no AI closers. */

export const STAND_IN =
  "The books start at equal weight. Change a weight, then stamp the sundial. A stamp scores that day only when every book and the bench have a print. A missing print does not score.";

export const RULES: readonly string[] = [
  "Click a floor tile. You walk there.",
  "Right-click a tile for Stamp, Examine, Rules, or Cancel.",
  "Left-click a book to pick it. Right-click that slot to add or shed weight.",
  "Stamp the sundial to score the day. If that day has no print, the stamp does not score.",
];
