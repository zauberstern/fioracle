import { describe, expect, it } from "vitest";
import {
  dollarDelta,
  feelLine,
  gistTag,
  rankBasket,
  trailReturns,
  type BookMove,
} from "./cashFeel";

describe("dollarDelta", () => {
  it("applies a tape return to the pile", () => {
    expect(dollarDelta(100_000, 0.012)).toBe(1200);
    expect(dollarDelta(100_000, -0.02)).toBe(-2000);
    expect(dollarDelta(100_000, null)).toBeNull();
  });
});

describe("trailReturns", () => {
  it("keeps finite daily_return rows on or before the pin", () => {
    const rows = [
      { as_of: "2008-01-01", daily_return: 0.01 },
      { as_of: "2008-02-01", daily_return: null },
      { as_of: "2008-03-01", daily_return: -0.02 },
      { as_of: "2008-04-01", daily_return: 0.03 },
    ];
    expect(trailReturns(rows, "2008-03-15", 6)).toEqual([0.01, -0.02]);
    expect(trailReturns(rows, "2008-04-01", 1)).toEqual([0.03]);
  });
});

describe("rankBasket", () => {
  const moves: BookMove[] = [
    {
      id: "cash",
      name: "US T-bills",
      group: "Cash",
      cash: true,
      ret: 0.001,
      trail: [0.001, 0.001, 0.001],
    },
    {
      id: "hy",
      name: "US junk bonds",
      group: "US credit",
      ret: 0.04,
      trail: [0.02, 0.03, 0.05, 0.04],
    },
    {
      id: "ig",
      name: "US company bonds",
      group: "US credit",
      ret: 0.01,
      trail: [0.008, 0.01, 0.012, 0.01],
    },
    {
      id: "oil",
      name: "Oil",
      group: "Commodities",
      ret: -0.03,
      trail: [-0.02, 0.01, -0.08, -0.03],
    },
    {
      id: "ust",
      name: "US Treasuries",
      group: "US rates",
      ret: 0.008,
      trail: [0.007, 0.008, 0.009, 0.008],
    },
  ];

  it("builds group pies for best, smooth, and worst mixes, and keeps cash aside", () => {
    const ranked = rankBasket(moves, 100_000);
    expect(ranked.cash?.delta).toBe(100);

    expect(ranked.best.slices.map((s) => s.group)).toEqual([
      "US credit",
      "US rates",
    ]);
    const bestCredit = ranked.best.slices.find((s) => s.group === "US credit")!;
    const bestRates = ranked.best.slices.find((s) => s.group === "US rates")!;
    // weights: hy 0.04, ig 0.01, ust 0.008 → credit 0.05/0.058, rates 0.008/0.058
    expect(bestCredit.pct).toBeCloseTo((0.05 / 0.058) * 100, 5);
    expect(bestRates.pct).toBeCloseTo((0.008 / 0.058) * 100, 5);
    expect(ranked.best.slices.reduce((a, s) => a + s.pct, 0)).toBeCloseTo(100, 5);
    expect(ranked.best.delta).toBeCloseTo(
      100_000 * ((0.04 * 0.04 + 0.01 * 0.01 + 0.008 * 0.008) / 0.058),
      5
    );

    expect(ranked.smooth.slices[0]?.group).toBe("US rates");
    expect(ranked.smooth.slices.reduce((a, s) => a + s.pct, 0)).toBeCloseTo(
      100,
      5
    );

    expect(ranked.worst.slices).toEqual([{ group: "Commodities", pct: 100 }]);
    expect(ranked.worst.delta).toBe(-3000);

    expect(ranked.best.slices.every((s) => s.group !== "Cash")).toBe(true);
  });
});

describe("gistTag", () => {
  it("labels a quiet pile that missed a runner", () => {
    expect(
      gistTag({
        word: "Quiet",
        cashDelta: 12,
        bestDelta: 1800,
        worstDelta: -40,
        hotDelta: 200,
      })
    ).toBe("left on read");
  });

  it("labels a stretched book that fell", () => {
    expect(
      gistTag({
        word: "Stretched",
        cashDelta: 10,
        bestDelta: 80,
        worstDelta: -900,
        hotDelta: -400,
      })
    ).toBe("piano overhead");
  });

  it("labels stretched cash that missed a run", () => {
    expect(
      gistTag({
        word: "Stretched",
        cashDelta: 10,
        bestDelta: 2200,
        worstDelta: -50,
        hotDelta: 2200,
      })
    ).toBe("FOMO meter");
  });
});

describe("feelLine", () => {
  it("states direct cash move, indirect miss, and heat without naming a single book as the portfolio", () => {
    const line = feelLine({
      amount: 100000,
      currency: "USD",
      date: "12 Jan 2026",
      cashName: "US T-bills",
      cashDelta: 14,
      bestDelta: 1840,
      worstDelta: -310,
      heat: 72,
      word: "Stretched",
    });
    expect(line).toMatch(/12 Jan 2026/);
    expect(line).toMatch(/100,000 USD/);
    expect(line).toMatch(/US T-bills/);
    expect(line).toMatch(/direct/i);
    expect(line).toMatch(/indirect/i);
    expect(line).toMatch(/Stretched/);
    expect(line).toMatch(/72/);
    expect(line).toMatch(/group/);
    expect(line).not.toMatch(/US junk bonds/);
    expect(line).not.toMatch(/Sharpe/);
    expect(line).not.toMatch(/forecast/);
    expect(line).not.toMatch(/—/);
  });
});
