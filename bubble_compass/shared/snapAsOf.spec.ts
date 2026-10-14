import { describe, expect, it } from "vitest";
import { snapAsOfIso, snapFrameIndex } from "./snapAsOf";

describe("snapAsOfIso", () => {
  it("returns null when the pin is before every row (no first-row fallthrough)", () => {
    const layers = {
      dlinear: [
        { as_of: "2020-01-02", residual_z: 0.1 },
        { as_of: "2024-06-03", residual_z: 9.9 },
      ],
    };
    expect(snapAsOfIso(layers, "2008-01-02")).toBeNull();
  });

  it("returns the latest on-or-before date", () => {
    const layers = {
      dlinear: [
        { as_of: "2008-01-01", residual_z: 0.1 },
        { as_of: "2008-08-22", residual_z: 1.2 },
        { as_of: "2026-10-02", residual_z: 2 },
      ],
    };
    expect(snapAsOfIso(layers, "2008-09-15")).toBe("2008-08-22");
  });
});

describe("snapFrameIndex", () => {
  it("returns -1 when the pin is before every date", () => {
    expect(snapFrameIndex(["2020-01-02", "2024-06-03"], "2008-01-02")).toBe(-1);
  });

  it("returns the latest on-or-before index", () => {
    expect(
      snapFrameIndex(["2008-01-01", "2008-08-22", "2026-10-02"], "2008-09-15")
    ).toBe(1);
  });
});
