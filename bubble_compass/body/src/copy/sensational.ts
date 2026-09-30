import { glossary, heatBandLabel, regimeKey } from "./glossary";

export function crisisHeadline(asset: string, score: number): string {
  return `${asset}: OVERHEAT ${score.toFixed(0)} - markets this stretched rarely end quietly`;
}

export function storyLead(
  asset: string,
  score: number,
  regime: "normal" | "boom" | "bust",
  asOf: string
): string {
  const heat = glossary[heatBandLabel(score)].label;
  const state = glossary[regimeKey(regime)].label;
  return `On ${asOf}, ${asset} read ${heat} at ${score.toFixed(1)}. Market state: ${state}.`;
}

export function stretchHeadline(bubbleFlag: boolean, stat: number, cv: number): string {
  if (bubbleFlag) {
    return `Explosive Growth Detected (stat ${stat.toFixed(2)} > ${cv.toFixed(2)})`;
  }
  return `Stretch quiet for now (stat ${stat.toFixed(2)} vs ${cv.toFixed(2)})`;
}
