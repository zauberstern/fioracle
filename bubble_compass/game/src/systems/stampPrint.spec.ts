import { describe, expect, it } from "vitest";
import { decideStampPrint } from "./stampPrint";

describe("decideStampPrint", () => {
  it("rejects NaN sleeve returns (no scoreTurn)", () => {
    const d = decideStampPrint(
      ["A", "B"],
      { A: 0.01, B: Number.NaN },
      0.0
    );
    expect(d.kind).toBe("no_print");
  });

  it("rejects non-finite bench", () => {
    const d = decideStampPrint(["A"], { A: 0.01 }, Number.NaN);
    expect(d.kind).toBe("no_print");
  });

  it("accepts finite zero as a real quiet day", () => {
    const d = decideStampPrint(["A"], { A: 0 }, 0);
    expect(d).toEqual({ kind: "score", returns: { A: 0 }, benchRet: 0 });
  });
});
