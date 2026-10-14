import { describe, expect, it } from "vitest";
import home from "../../../../docs/index.html?raw";
import { MACHINERY } from "./scoreCopy";
import { pitchPlain } from "./pitchCopy";

function words(text: string): number {
  return text.split(/\s+/).filter((w) => w.length > 0).length;
}

describe("pitchPlain", () => {
  const text = pitchPlain();

  it("names the score and keeps the weights in the equations", () => {
    expect(text).toMatch(/Park cash on the week page/);
    expect(text).toMatch(/direct mark/);
    expect(text).toMatch(/indirect miss/);
    expect(text).toMatch(/three small pies/);
    expect(text).toMatch(/Quiet is under 40/);
    expect(text).toMatch(/Warming starts at 40/);
    expect(text).toMatch(/Stretched starts at 70/);
    expect(text).toMatch(/stops at 100/);
    expect(text).toMatch(/DLinear/);
    expect(text).toMatch(/Phillips-Shi-Yu/);
    expect(text).toMatch(/log-periodic/);
    expect(text).toMatch(/\\times 12/);
    expect(text).toMatch(/\\min\(40/);
    expect(text).toMatch(/25 \+ \\max\(0, s - c\) \\times 8/);
    expect(text).toMatch(/\\times 5/);
    expect(text).toMatch(/\\times 30/);
    expect(text).toMatch(/\\times 15/);
    expect(text).toMatch(/\\min\(100/);
    expect(text).toMatch(/12 points/);
    expect(text).toMatch(/stops at 40/);
    expect(text).toMatch(/below the path adds 0/);
    expect(text).toMatch(/starts at 25/);
    expect(text).toMatch(/adds 8/);
    expect(text).toMatch(/1\.49/);
    expect(text).toMatch(/five times the reading/);
    expect(text).toMatch(/reading below zero adds 0/);
    expect(text).toMatch(/up to 30/);
    expect(text).toMatch(/up to 15/);
    expect(text).toMatch(/each adds 0/);
    expect(text).toMatch(/Cash is held at 0/);
    expect(text).toMatch(/on or before/);
    expect(text).toMatch(/normal on every row, including 2020/);
    expect(text).toMatch(/oil book/);
    expect(text).toMatch(/US inflation-linked/);
    expect(text).toMatch(/Swiss franc/);
    expect(text).toMatch(/only the fast-rise check can move its heat/);
    expect(text).toMatch(/Phillips, Shi and Yu \(2015\)/);
    expect(text).toMatch(/They are not a forecast or a recommendation\./);
    expect(text).not.toMatch(/Late 2026/);
    expect(text).not.toMatch(/shown to be a discovery/);
    expect(text).toMatch(/Limits/);
    expect(words(text)).toBeGreaterThan(200);
  });

  it("does not borrow a performance claim or a forbidden paper", () => {
    expect(text).not.toMatch(/\u2014/);
    expect(text).not.toMatch(/Sharpe|ERoD|eighty-seven|household/i);
    expect(text).not.toMatch(/\bI\b|\bwe\b/);
    expect(text).not.toMatch(/CL-00\d|2508\.15667|jump model/i);
    expect(text).not.toMatch(/docs\/|\.json|\.py/);
  });
});

describe("MACHINERY", () => {
  it("stays the short formula under the week page", () => {
    expect(MACHINERY).toHaveLength(5);
    expect(MACHINERY.join(" ")).not.toMatch(/Grinold|Noguer/);
  });
});

describe("static pages", () => {
  it("drops the unnamed literature claim from the desk page", () => {
    expect(home).not.toMatch(/academic literature says/);
    expect(home).not.toMatch(/published literature/);
  });
});
