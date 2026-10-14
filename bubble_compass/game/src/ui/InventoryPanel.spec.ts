import { describe, expect, it } from "vitest";
import { ScoreKeeper } from "../systems/ScoreKeeper";
import { Portfolio } from "../entities/Portfolio";
import { weightsToQty } from "./InventoryPanel";
import universe from "../data/universe.json";

const ids = universe.sleeves.map((s) => s.id);

describe("weightsToQty", () => {
  it("sums to 100 for equal eight-sleeve book", () => {
    const w = 1 / ids.length;
    const weights = Object.fromEntries(ids.map((id) => [id, w]));
    const qty = weightsToQty(weights, ids);
    const sum = Object.values(qty).reduce((a, b) => a + b, 0);
    expect(sum).toBe(100);
    const each = Math.round(100 / ids.length);
    for (const id of ids) {
      expect(Math.abs((qty[id] ?? 0) - each)).toBeLessThanOrEqual(1);
    }
  });

  it("sums to 100 for all-in cash", () => {
    const weights = Object.fromEntries(ids.map((id) => [id, 0]));
    weights.US_CASH_RETURN = 1;
    const qty = weightsToQty(weights, ids);
    expect(Object.values(qty).reduce((a, b) => a + b, 0)).toBe(100);
    expect(qty.US_CASH_RETURN).toBe(100);
  });

  it("sums to 100 after bumpSelected(0.05)", () => {
    const p = new Portfolio();
    p.selectIndex(0);
    p.bumpSelected(0.05);
    const qty = weightsToQty(p.weights, ids);
    expect(Object.values(qty).reduce((a, b) => a + b, 0)).toBe(100);
  });

  it("bumpSelected does not change ScoreKeeper total", () => {
    const sk = new ScoreKeeper();
    const p = new Portfolio();
    expect(sk.totalScore).toBe(0);
    p.selectIndex(1);
    p.bumpSelected(0.05);
    expect(sk.totalScore).toBe(0);
  });

  it("all-zero weights put 100 on cash, not the last catalog id", () => {
    const weights = Object.fromEntries(ids.map((id) => [id, 0]));
    const qty = weightsToQty(weights, ids);
    expect(Object.values(qty).reduce((a, b) => a + b, 0)).toBe(100);
    expect(qty.US_CASH_RETURN).toBe(100);
    expect(qty.CDX_IG_5Y_TOTAL_RETURN).toBe(0);
  });
});

