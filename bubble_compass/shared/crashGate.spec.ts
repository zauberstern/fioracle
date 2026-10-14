import { describe, expect, it } from "vitest";
import { evaluateCrashGate } from "./crashGate";

describe("evaluateCrashGate", () => {
  it("triggers on heat >= 70", () => {
    const r = evaluateCrashGate({
      heat: 70,
      bubbleFlag: false,
      stretch: 0,
      criticalValue: 1.49,
      portfolioReturn: 0.01,
    });
    expect(r.triggered).toBe(true);
    expect(r.reason).toContain("heat");
  });

  it("triggers on bubble_flag with loss", () => {
    const r = evaluateCrashGate({
      heat: 10,
      bubbleFlag: true,
      stretch: 0,
      criticalValue: 1.49,
      portfolioReturn: -0.025,
    });
    expect(r.triggered).toBe(true);
    expect(r.reason).toContain("bubble_flag");
  });

  it("does not trigger on bubble_flag without loss", () => {
    const r = evaluateCrashGate({
      heat: 10,
      bubbleFlag: true,
      stretch: 0,
      criticalValue: 1.49,
      portfolioReturn: -0.01,
    });
    expect(r.triggered).toBe(false);
  });

  it("triggers on stretch breach with loss", () => {
    const r = evaluateCrashGate({
      heat: 10,
      bubbleFlag: false,
      stretch: 2.1,
      criticalValue: 1.49,
      portfolioReturn: -0.03,
    });
    expect(r.triggered).toBe(true);
    expect(r.reason).toContain("stretch");
  });
});
