import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScoreKeeper } from "./ScoreKeeper";
import { TownMemory } from "./TownMemory";

describe("TownMemory", () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => {
        store.set(k, v);
      },
      clear: () => store.clear(),
      removeItem: (k: string) => {
        store.delete(k);
      },
    });
  });

  it("increments a district once per enter, not while standing", () => {
    const m = new TownMemory();
    expect(m.enterDistrict("SP500_TOTAL_RETURN")).toBe(1);
    expect(m.enterDistrict("SP500_TOTAL_RETURN")).toBe(1);
    expect(m.enterDistrict(null)).toBe(0);
    expect(m.enterDistrict("SP500_TOTAL_RETURN")).toBe(2);
  });

  it("outline tiers at 3 and 9", () => {
    const m = new TownMemory();
    for (let i = 0; i < 3; i++) {
      m.enterDistrict(null);
      m.enterDistrict("GOLD_TOTAL_RETURN");
    }
    expect(m.outlineTier("GOLD_TOTAL_RETURN")).toBe(1);
    for (let i = 0; i < 6; i++) {
      m.enterDistrict(null);
      m.enterDistrict("GOLD_TOTAL_RETURN");
    }
    expect(m.outlineTier("GOLD_TOTAL_RETURN")).toBe(2);
  });

  it("tour complete only after all five stones", () => {
    const m = new TownMemory();
    const dates = [
      "2008-01-02",
      "2008-09-15",
      "2020-03-16",
      "2022-01-03",
      "2023-03-10",
    ];
    expect(m.tourLine(dates)).toBeNull();
    for (const d of dates.slice(0, 4)) m.touchStone(d);
    expect(m.tourLine(dates)).toBeNull();
    m.touchStone(dates[4]!);
    expect(m.tourLine(dates)).toBe(
      "You have touched every flood stone. Those dates are the public ones."
    );
  });

  it("visit increment does not change ScoreKeeper.totalScore", () => {
    const score = new ScoreKeeper();
    const before = score.totalScore;
    const m = new TownMemory();
    m.enterDistrict("SP500_TOTAL_RETURN");
    m.touchStone("2008-01-02");
    expect(score.totalScore).toBe(before);
  });
});
