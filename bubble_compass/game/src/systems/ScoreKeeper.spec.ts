import { describe, expect, it } from "vitest";
import { ScoreKeeper } from "./ScoreKeeper";
import universe from "../data/universe.json";

describe("ScoreKeeper", () => {
  it("includes portfolio P&L in total", () => {
    const sk = new ScoreKeeper();
    const weights: Record<string, number> = {};
    for (const s of universe.sleeves) weights[s.id] = 0;
    weights[universe.benchmark] = 1;
    const returns: Record<string, number> = {};
    for (const s of universe.sleeves) returns[s.id] = 0;
    returns[universe.benchmark] = 0.01;
    const bd = sk.scoreTurn(weights, returns, 0.01);
    expect(bd.portfolioReturn).toBeCloseTo(0.01, 6);
    expect(bd.total).toBeGreaterThan(0.005);
  });

  it("cash-heavy book is not optimal vs invested when returns positive", () => {
    const skCash = new ScoreKeeper();
    const skInv = new ScoreKeeper();
    const cash: Record<string, number> = {};
    const inv: Record<string, number> = {};
    const returns: Record<string, number> = {};
    for (const s of universe.sleeves) {
      cash[s.id] = 0;
      inv[s.id] = 1 / universe.sleeves.length;
      returns[s.id] = 0.02;
    }
    // Simulate cash as zero weights renormalized - equal tiny; use all-zero -> resetEqual
    // Compare concentrated cash-like (first sleeve 1e-6, rest 0 renormalized to equal)
    // vs equal invested: both equal after renormalize. Instead compare all-in cash sleeve
    // with 0 spread vs equity with positive return by forcing weights.
    const cashW = { ...cash };
    cashW[universe.sleeves.find((s) => s.spreadBps === 0 && s.elBps <= 2)?.id ?? universe.benchmark] = 1;
    for (const id of Object.keys(cashW)) {
      if (cashW[id] !== 1) cashW[id] = 0;
    }
    // Zero returns for "cash-like" day vs positive equity print
    const flat: Record<string, number> = {};
    const up: Record<string, number> = {};
    for (const s of universe.sleeves) {
      flat[s.id] = 0;
      up[s.id] = s.id === universe.benchmark ? 0.03 : 0.01;
    }
    const cashScore = skCash.scoreTurn(cashW, flat, 0).total;
    const invScore = skInv.scoreTurn(inv, up, 0.03).total;
    expect(invScore).toBeGreaterThan(cashScore);
  });

  it("does not apply concentration HHI tax", () => {
    const sk = new ScoreKeeper();
    const w: Record<string, number> = {};
    for (const s of universe.sleeves) w[s.id] = 0;
    w[universe.benchmark] = 1;
    const ret: Record<string, number> = {};
    for (const s of universe.sleeves) ret[s.id] = 0;
    const bd = sk.scoreTurn(w, ret, 0);
    // HHI present as diagnostic; total should not subtract large HHI penalty
    expect(bd.hhi).toBeGreaterThan(0);
    expect(Math.abs(bd.total)).toBeLessThan(0.01);
  });
});
