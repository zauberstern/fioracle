import { describe, expect, it } from "vitest";
import { heroFromCards, sentenceFor } from "./readingCopy";

describe("heroFromCards", () => {
  it("is not Quiet when a non-cash card is Warming", () => {
    const hero = heroFromCards([
      { name: "Stocks", heat: 16 },
      { name: "High-yield credit", heat: 46 },
      { name: "Cash", heat: 87, cash: true },
    ]);
    expect(hero.word).toBe("Warming");
    expect(hero.heat).toBe(46);
    expect(hero.leaderName).toBe("High-yield credit");
    expect(hero.sentence).not.toMatch(/sit quiet/i);
    expect(hero.sentence).not.toMatch(/rose/i);
    expect(hero.sentence).toMatch(/Heat is 46/);
  });

  it("ignores cash heat for the hero", () => {
    const hero = heroFromCards([
      { name: "Stocks", heat: 10 },
      { name: "Cash", heat: 90, cash: true },
    ]);
    expect(hero.word).toBe("Quiet");
    expect(hero.heat).toBe(10);
  });

  it("empty crowd is Loading, not Quiet", () => {
    const hero = heroFromCards([]);
    expect(hero.word).toBe("Loading");
    expect(hero.sentence).not.toMatch(/sit quiet/i);
  });

  it("matches card word on unrounded heat at 39.6 and 69.6", () => {
    expect(heroFromCards([{ name: "A", heat: 39.6 }]).word).toBe("Quiet");
    expect(heroFromCards([{ name: "B", heat: 69.6 }]).word).toBe("Warming");
  });
});

describe("sentenceFor", () => {
  it("does not invent a last-week rise", () => {
    expect(
      sentenceFor("Warming", 50, "Gold", [
        "Residual z is 1.10, which adds 13.2 points.",
        "The stretch statistic is 0.40 against a critical value of 1.49. The flag is off, so this piece adds 2.0 points.",
      ])
    ).toBe(
      "Gold leads. Heat is 50. Residual z is 1.10, which adds 13.2 points. The stretch statistic is 0.40 against a critical value of 1.49. The flag is off, so this piece adds 2.0 points."
    );
  });
});
