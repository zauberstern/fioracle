import universe from "../data/universe.json";
import type { Portfolio } from "../entities/Portfolio";

export interface TurnScoreBreakdown {
  spreadEarned: number;
  expectedLoss: number;
  delayedRealizedLoss: number;
  capitalUsed: number;
  concentrationPenalty: number;
  portfolioReturn: number;
  total: number;
}

const BPS = 1 / 10000;
const DELAY_LAG = 2;

export class ScoreKeeper {
  private realizedLossHistory: number[] = [];
  private cumulativeScore = 0;

  resetSession(): void {
    this.realizedLossHistory = [];
    this.cumulativeScore = 0;
  }

  get totalScore(): number {
    return this.cumulativeScore;
  }

  elWeightedHhi(weights: Record<string, number>): number {
    const sleeves = universe.sleeves;
    let elSum = 0;
    const elWeights: Record<string, number> = {};
    for (const s of sleeves) {
      const w = weights[s.id] ?? 0;
      const el = s.elBps * BPS;
      elWeights[s.id] = w * el;
      elSum += elWeights[s.id];
    }
    if (elSum <= 0) return 0;
    let hhi = 0;
    for (const s of sleeves) {
      const share = (elWeights[s.id] ?? 0) / elSum;
      hhi += share * share;
    }
    return hhi;
  }

  scoreTurn(portfolio: Portfolio, sleeveReturns: Record<string, number>): TurnScoreBreakdown {
    const weights = portfolio.weights;
    let portfolioReturn = 0;
    let spreadEarned = 0;
    let expectedLoss = 0;
    let capitalUsed = 0;

    for (const s of universe.sleeves) {
      const w = weights[s.id] ?? 0;
      const r = sleeveReturns[s.id] ?? 0;
      portfolioReturn += w * r;
      spreadEarned += w * s.spreadBps * BPS / 252;
      expectedLoss += w * s.elBps * BPS / 252;
      if (s.riskBucket !== "cash") capitalUsed += w;
    }

    const rawLoss = Math.max(0, -portfolioReturn);
    this.realizedLossHistory.push(rawLoss);
    const lagIdx = this.realizedLossHistory.length - 1 - DELAY_LAG;
    const delayedRealizedLoss =
      lagIdx >= 0 ? this.realizedLossHistory[lagIdx] * 0.5 : 0;

    const hhi = this.elWeightedHhi(weights);
    const concentrationPenalty = hhi * 0.15;

    const total =
      spreadEarned -
      expectedLoss -
      delayedRealizedLoss -
      capitalUsed * 0.002 -
      concentrationPenalty;

    this.cumulativeScore += total;

    return {
      spreadEarned,
      expectedLoss,
      delayedRealizedLoss,
      capitalUsed,
      concentrationPenalty,
      portfolioReturn,
      total,
    };
  }
}
