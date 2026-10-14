import { describe, expect, it } from "vitest";
import { readBook } from "../narrator/scoreCopy";
import { diagLines, oddsPercent } from "./diagReading";

const layers = {
  dlinear: [
    { as_of: "2008-07-24", residual_z: 0, daily_return: 0.01 },
    { as_of: "2008-08-22", residual_z: -0.23, daily_return: -0.01 },
  ],
  bsadf: [
    {
      as_of: "2008-07-24",
      bsadf_stat: 3.06,
      critical_value: 1.49,
      bubble_flag: false,
    },
    {
      as_of: "2008-08-22",
      bsadf_stat: 0.88,
      critical_value: 1.49,
      bubble_flag: false,
    },
  ],
  lppls: [{ as_of: "2008-08-22", unavailable: true }],
  sentiment: [{ as_of: "2008-08-22", unavailable: true }],
};

describe("oddsPercent", () => {
  it("treats a fraction and a percent the same way as the regime chart", () => {
    expect(oddsPercent(0.2)).toBe(20);
    expect(oddsPercent(40)).toBe(40);
    expect(oddsPercent(null)).toBeNull();
  });
});

describe("diagLines", () => {
  it("reads Stocks on the Lehman row in five lines", () => {
    const book = { name: "Stocks" };
    const now = readBook(book, layers, "2008-08-22");
    const prev = readBook(book, layers, "2008-07-24");
    const lines = diagLines({
      name: "Stocks",
      now,
      prev: { word: prev.word, heat: prev.heat },
      nowDate: "2008-08-22",
      prevDate: "2008-07-24",
      boom: 20,
      bust: 40,
      prevBoom: 20,
      prevBust: 30,
    });
    expect(lines).toHaveLength(5);
    expect(lines[0]).toMatch(/Quiet at 4\.4/);
    expect(lines[0]).toMatch(/24 Jul 2008/);
    expect(lines[1]).toMatch(/0\.23 steps below/);
    expect(lines[2]).toMatch(/0\.88/);
    expect(lines[2]).toMatch(/1\.49/);
    expect(lines[2]).toMatch(/adds 4\.4/);
    expect(lines[3]).toMatch(/Boom is 20 percent and bust is 40 percent/);
    expect(lines[3]).toMatch(/recorded state stays normal/);
    expect(lines[4]).toMatch(/each adds 0/);
    expect(lines.join(" ")).not.toMatch(/\u2014|Grinold|Noguer|Sharpe/);
  });

  it("says boom and bust matched when the percents do not move", () => {
    const book = { name: "Stocks" };
    const now = readBook(book, layers, "2008-08-22");
    const prev = readBook(book, layers, "2008-07-24");
    const lines = diagLines({
      name: "Stocks",
      now,
      prev: { word: prev.word, heat: prev.heat },
      nowDate: "2008-08-22",
      prevDate: "2008-07-24",
      boom: 20,
      bust: 40,
      prevBoom: 20,
      prevBust: 40,
    });
    expect(lines[3]).toBe(
      "Boom and bust match the prior row. The recorded state stays normal."
    );
  });
});
