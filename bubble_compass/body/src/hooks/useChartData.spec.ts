import { describe, expect, it } from "vitest";
import { chartRows, plotFastRise, rowAtPin, sliceByCutoff, uniqueByTime } from "./useChartData";

describe("plotFastRise", () => {
  it("keeps an ordinary reading and pins a huge one at the top", () => {
    expect(plotFastRise(0.63)).toBe(0.63);
    expect(plotFastRise(1.49)).toBe(1.49);
    expect(plotFastRise(1301716.79)).toBe(8);
    expect(plotFastRise(-0.4)).toBe(-0.4);
    expect(plotFastRise(Number.NaN)).toBe(0);
  });
});

describe("uniqueByTime", () => {
  it("keeps the later point when two rows share a time", () => {
    const rows = uniqueByTime([
      { time: 20, value: 1 },
      { time: 10, value: 2 },
      { time: 20, value: 3 },
    ]);
    expect(rows.map((r) => r.time)).toEqual([10, 20]);
    expect(rows[1]?.value).toBe(3);
  });
});

describe("chartRows", () => {
  const rows = [
    { time: 10, value: 1 },
    { time: 20, value: 2 },
    { time: 30, value: 3 },
  ];

  it("keeps rows after the pin when the chart shows the whole history", () => {
    expect(chartRows(rows, 20, true)).toEqual(rows);
    expect(chartRows(rows, 20, false)).toEqual(rows.slice(0, 2));
  });

  it("reads the row on the pin without dropping later rows from the series", () => {
    expect(rowAtPin(rows, 20)?.value).toBe(2);
    expect(rowAtPin(rows, 15)?.value).toBe(1);
  });
});

describe("sliceByCutoff", () => {
  it("drops rows after the pinned time", () => {
    const rows = sliceByCutoff(
      [
        { time: 10, value: 1 },
        { time: 30, value: 2 },
      ],
      20
    );
    expect(rows).toEqual([{ time: 10, value: 1 }]);
  });
});
