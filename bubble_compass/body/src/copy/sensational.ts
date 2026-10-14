import { glossary, heatBandLabel, regimeKey } from "./glossary";

export function crisisHeadline(asset: string, score: number): string {
  return `${asset} heat ${score.toFixed(0)}. The reading is stretched.`;
}

export function storyLead(
  asset: string,
  score: number,
  regime: "normal" | "boom" | "bust",
  asOf: string
): string {
  const heat = glossary[heatBandLabel(score)].label;
  const state = glossary[regimeKey(regime)].label;
  return `On ${asOf}, ${asset} read ${heat}, heat ${score.toFixed(1)}. Market state: ${state}.`;
}

export function stretchHeadline(bubbleFlag: boolean, stat: number, cv: number): string {
  if (bubbleFlag) {
    return `The check is on (stat ${stat.toFixed(2)} above ${cv.toFixed(2)})`;
  }
  return `The check is off (stat ${stat.toFixed(2)} vs ${cv.toFixed(2)})`;
}
