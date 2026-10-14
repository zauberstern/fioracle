import { describe, expect, it } from "vitest";
import {
  examineBook,
  examineDistrict,
  examineFlatDay,
  examineStretchStone,
  examineSundial,
} from "./Examine";
import type { DistrictDef } from "../world/TownLayout";

const district: DistrictDef = {
  sleeveId: "SP500_TOTAL_RETURN",
  place: "Standing Grove",
  verb: "Chop",
  tool: "tool_axe",
  tx: 16,
  ty: 4,
};

describe("examine lines", () => {
  it("names weight, stamp, and score without ore, mass, or crack", () => {
    const lines = [
      examineSundial("2024-06-03"),
      examineFlatDay(),
      examineStretchStone({
        heat: 10,
        stretch: 1.2,
        criticalValue: 0.5,
        bubbleFlag: false,
        regime: "normal",
        sentiment: 0,
        spreadBps: 0,
        crashWindow: "-",
      } as never),
      examineDistrict(district, 0.125, 0.01),
      examineBook("2024-06-03", 10, 1.2, 0.5, 1, {
        sleeveId: "SP500_TOTAL_RETURN",
        visitCount: 2,
      }),
    ];
    for (const line of lines) {
      expect(line).not.toMatch(/\b(ore|mass|crack)\b/i);
      expect(line).not.toMatch(/SP500_TOTAL_RETURN/);
    }
    const districtLine = lines[3] ?? "";
    expect(districtLine).toMatch(/weight/i);
    expect(districtLine).toMatch(/stamp/i);
    expect(districtLine).toMatch(/score/i);
    expect(districtLine).toMatch(/Stocks/);
    expect(lines[0]).toMatch(/stamp/i);
    expect(lines[0]).toMatch(/score/i);
    expect(lines[4]).toMatch(/Visits to this book: 2/);
  });
});