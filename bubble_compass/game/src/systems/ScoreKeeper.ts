import universe from "../data/universe.json";

export interface TurnScoreBreakdown {
  spreadEarned: number;
  expectedLoss: number;
  delayedRealizedLoss: number;
  portfolioReturn: number;
  benchReturn: number;
  skillVsBench: number;
  turnover: number;
  hhi: number;
  total: number;
}

const BPS = 1 / 10000;
const DELAY_LAG = 2;

export class ScoreKeeper {
  private realizedLossHistory: number[] = [];
  private cumulativeScore = 0;
  private prevWeights: Record<string, number> | null = null;
  private maxDrawdown = 0;
  private equity = 1;

  resetSession(): void {
    this.realizedLossHistory = [];
    this.cumulativeScore = 0;
    this.prevWeights = null;
    this.maxDrawdown = 0;
    this.equity = 1;
  }

  get totalScore(): number {
    return this.cumulativeScore;
  }

  get peakDrawdown(): number {
    return this.maxDrawdown;
  }

  elWeightedHhi(weights: Record<string, number>): number {
    const sleeves = universe.sleeves;
    let elSum = 0;
    const elWeights: Record<string, number> = {};
    for (const s of sleeves) {
      const w = weights[s.id] ?? 0;
      const el = s.elBps * BPS;
      elWeights[s.id] = w * el;
      elSum += elWeights[s.id]!;
    }
    if (elSum <= 0) return 0;
    let hhi = 0;
    for (const s of sleeves) {
      const share = (elWeights[s.id] ?? 0) / elSum;
      hhi += share * share;
    }
    return hhi;
  }

  scoreTurn(
    weights: Record<string, number>,
    sleeveReturns: Record<string, number>,
    benchReturn: number
  ): TurnScoreBreakdown {
    let portfolioReturn = 0;
    let spreadEarned = 0;
    let expectedLoss = 0;

    for (const s of universe.sleeves) {
      const w = weights[s.id] ?? 0;
      const r = sleeveReturns[s.id] ?? 0;
      portfolioReturn += w * r;
      spreadEarned += (w * s.spreadBps * BPS) / 252;
      expectedLoss += (w * s.elBps * BPS) / 252;
    }

    let turnover = 0;
    if (this.prevWeights) {
      for (const s of universe.sleeves) {
        turnover += Math.abs((weights[s.id] ?? 0) - (this.prevWeights[s.id] ?? 0));
      }
      turnover *= 0.5;
    }
    this.prevWeights = { ...weights };

    const rawLoss = Math.max(0, -portfolioReturn);
    this.realizedLossHistory.push(rawLoss);
    const lagIdx = this.realizedLossHistory.length - 1 - DELAY_LAG;
    const delayedRealizedLoss =
      lagIdx >= 0 ? this.realizedLossHistory[lagIdx]! * 0.5 : 0;

    const skillVsBench = 0.25 * (portfolioReturn - benchReturn);
    const hhi = this.elWeightedHhi(weights);

    const total =
      portfolioReturn +
      skillVsBench +
      spreadEarned -
      expectedLoss -
      delayedRealizedLoss -
      0.0005 * turnover;

    this.cumulativeScore += total;
    this.equity *= 1 + portfolioReturn;
    this.maxDrawdown = Math.min(this.maxDrawdown, this.equity - 1);

    return {
      spreadEarned,
      expectedLoss,
      delayedRealizedLoss,
      portfolioReturn,
      benchReturn,
      skillVsBench,
      turnover,
      hhi,
      total,
    };
  }
}
