import { describe, expect, it } from "vitest";
import { evaluateCrashGate } from "../../../shared/crashGate";

/** Completeness contract: partial sleeve sets must not become api/static. */
describe("tape completeness contract", () => {
  it("documents required sleeve count", async () => {
    const universe = await import("../data/universe.json");
    expect(universe.sleeves.length).toBe(23);
  });

  it("crash gate ignores regime_state alone", () => {
    // Published tape often has regime_state=normal; gate uses heat/bubble/stretch.
    const r = evaluateCrashGate({
      heat: 20,
      bubbleFlag: false,
      stretch: 1.0,
      criticalValue: 1.49,
      portfolioReturn: -0.05,
    });
    expect(r.triggered).toBe(false);
  });
});
