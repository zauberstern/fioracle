import { describe, expect, it } from "vitest";
import { paintCell } from "./floorPaint";

describe("paintCell", () => {
  it("grass is olive", () => {
    expect(paintCell("grass").fill).toEqual([74, 92, 58]);
    expect(paintCell("grass").outline).toBeNull();
  });

  it("wall fill is stone1, not chrome stone0", () => {
    const w = paintCell("wall");
    expect(w.fill).toEqual([92, 83, 70]);
    expect(w.fill).not.toEqual([58, 52, 44]);
    expect(w.outline).toEqual([176, 141, 79]);
  });

  it("sundial has brass outline", () => {
    expect(paintCell("sundial").outline).toEqual([176, 141, 79]);
  });
});
