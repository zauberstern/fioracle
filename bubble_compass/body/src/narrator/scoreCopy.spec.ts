import { describe, expect, it } from "vitest";
import {
  MACHINERY,
  bookMarkSentence,
  heatClose,
  driverSentence,
  moveSentence,
  padSentence,
  pieceLines,
  playChangeSentence,
  readBook,
  sharedMarkSentences,
  spineSentence,
} from "./scoreCopy";
import type { HeatParts } from "./heat";

const quiet: HeatParts = {
  residual: 12,
  bsadf: 2.5,
  lppls: 0,
  sentiment: 0,
  heat: 14.5,
};

describe("driverSentence", () => {
  it("packs residual, stretch, and the two idle layers into one answer", () => {
    const text = driverSentence({
      residualZ: 1.558,
      bsadfStat: 2.793,
      criticalValue: 1.49,
      bubbleFlag: true,
      lpplsUnavailable: true,
      sentimentUnavailable: true,
    });
    expect(text).toMatch(/sits 1\.56 steps above/);
    expect(text).toMatch(/18\.7 points/);
    expect(text).toMatch(/fast-rise reading is 2\.79/);
    expect(text).toMatch(/check is on/);
    expect(text).toMatch(/35\.4 points/);
    expect(text).toMatch(/break date and news tone are not in this history/);
    expect(text).not.toMatch(/\u2014/);
  });
});

describe("pieceLines", () => {
  it("cites the four inputs that produce heat", () => {
    const lines = pieceLines(
      {
        residualZ: 1.031,
        bsadfStat: 0.63,
        criticalValue: 1.49,
        bubbleFlag: false,
        lpplsUnavailable: true,
        sentimentUnavailable: true,
      },
      quiet
    );
    expect(lines[0]).toBe(
      "It sits 1.03 steps above the path it had been following. That adds 12.0 points."
    );
    expect(lines[1]).toMatch(/check is off/);
    expect(lines[1]).toMatch(/1\.49/);
    expect(lines[1]).toMatch(/2\.5 points/);
    expect(lines[2]).toBe(
      "A date for a break is not in this history, so that part adds 0."
    );
    expect(lines[3]).toBe(
      "News tone is not in this history, so that part adds 0."
    );
    expect(lines.join(" ")).not.toMatch(/\u2014/);
  });
});

describe("moveSentence", () => {
  it("names the piece that moved", () => {
    const now: HeatParts = { ...quiet, bsadf: 8.5, heat: 20.5 };
    expect(moveSentence(now, quiet, 0.01)).toBe(
      "The fast-rise check moved up by 6.0 points from the prior row."
    );
  });

  it("says the pieces match and cites a zero return", () => {
    expect(moveSentence(quiet, quiet, 0)).toBe(
      "The four parts match the prior row. The book's return on this row is 0."
    );
  });

  it("says when the book has no earlier row", () => {
    expect(moveSentence(quiet, null, 0.02)).toBe(
      "There is no earlier row on this book."
    );
  });
});

describe("shared marks", () => {
  it("cites the 2 Oct 2026 shared fields and the spread unit change", () => {
    const lines = sharedMarkSentences({
      asOf: "2026-10-02",
      hyBps: 343,
      hyChange: -28,
      vix: 17.21,
      debt: 118.7817060238,
      gap: 8.7817060238,
      breach: false,
    });
    const text = lines.join(" ");
    expect(text).toMatch(/343 basis points/);
    expect(text).toMatch(/-28 basis points/);
    expect(text).toMatch(/1 Feb 2022/);
    expect(text).toMatch(/VIX on this row is 17.21/);
    expect(text).toMatch(/118\.78 percent of GDP/);
    expect(text).toMatch(/gap is 8\.78/);
    expect(text).toMatch(/not breached/);
    expect(text).not.toMatch(/\u2014/);
  });

  it("omits the 2022 unit note on a 2008 row", () => {
    const text = sharedMarkSentences({
      asOf: "2008-09-15",
      hyBps: 8.01,
      hyChange: 0.62,
      vix: 19.82,
      debt: 64.2,
      gap: 1.1,
      breach: false,
    }).join(" ");
    expect(text).toMatch(/8\.01 basis points/);
    expect(text).not.toMatch(/1 Feb 2022/);
  });
});

describe("book marks and spine", () => {
  it("states oil heat from the two live pieces", () => {
    const line = bookMarkSentence("Oil", {
      residual: 0,
      bsadf: 35,
      lppls: 0,
      sentiment: 0,
      heat: 35,
    }, true);
    expect(line).toMatch(/Oil heat is 35.0/);
    expect(line).toMatch(/fast-rise check is on and adds 35.0/);
    expect(line).toMatch(/total return/);
    expect(line).not.toMatch(/pump/);
  });

  it("counts the loaded tape with plain dates", () => {
    expect(spineSentence(23, 234, "2008-01-01", "2026-10-02")).toBe(
      "This history has 23 books and 234 rows, from 1 Jan 2008 through 2 Oct 2026."
    );
  });

  it("flags a row where every return is zero", () => {
    expect(padSentence([0, 0, 0])).toMatch(/return of 0/);
    expect(padSentence([0, 0.01])).toBeNull();
  });
});

describe("readBook", () => {
  it("scores cash at zero and skips the four pieces", () => {
    const reading = readBook(
      { name: "Cash", cash: true },
      {
        dlinear: [
          { as_of: "2026-09-03", residual_z: 4, daily_return: 0.01 },
          { as_of: "2026-10-02", residual_z: 4, daily_return: 0 },
        ],
        bsadf: [
          { as_of: "2026-09-03", bsadf_stat: 4, critical_value: 1.49, bubble_flag: true },
          { as_of: "2026-10-02", bsadf_stat: 4, critical_value: 1.49, bubble_flag: true },
        ],
        lppls: [{ as_of: "2026-10-02", unavailable: true }],
        sentiment: [{ as_of: "2026-10-02", unavailable: true }],
      },
      "2026-10-02"
    );
    expect(reading.heat).toBe(0);
    expect(reading.lines).toEqual([
      "Cash is left out of the ranking. Its score stays at 0.",
    ]);
  });

  it("uses the prior print for the move line", () => {
    const reading = readBook(
      { name: "Stocks" },
      {
        dlinear: [
          { as_of: "2026-09-03", residual_z: 0, daily_return: 0.02 },
          { as_of: "2026-10-02", residual_z: 1, daily_return: 0.01 },
        ],
        bsadf: [
          { as_of: "2026-09-03", bsadf_stat: 0.5, critical_value: 1.49, bubble_flag: false },
          { as_of: "2026-10-02", bsadf_stat: 0.5, critical_value: 1.49, bubble_flag: false },
        ],
        lppls: [
          { as_of: "2026-09-03", unavailable: true },
          { as_of: "2026-10-02", unavailable: true },
        ],
        sentiment: [
          { as_of: "2026-09-03", unavailable: true },
          { as_of: "2026-10-02", unavailable: true },
        ],
      },
      "2026-10-02"
    );
    expect(reading.heat).toBe(14.5);
    expect(reading.move).toMatch(/distance above its path moved up by 12.0 points/);
  });
});

describe("extreme stretch", () => {
  it("cites a huge statistic without an unbounded point total", () => {
    const stat = 1301716.7892094837;
    const bsadf = 25 + Math.max(0, stat - 1.49) * 8;
    const lines = pieceLines(
      {
        residualZ: 1.53,
        bsadfStat: stat,
        criticalValue: 1.49,
        bubbleFlag: true,
        lpplsUnavailable: true,
        sentimentUnavailable: true,
      },
      { residual: 18.4, bsadf, lppls: 0, sentiment: 0, heat: 100 }
    );
    expect(lines[1]).toMatch(/1,301,717/);
    expect(lines[1]).toMatch(/stops at 100/);
    expect(lines[1]).not.toMatch(/10413747/);
    const mark = bookMarkSentence("US inflation-linked", {
      residual: 18.4,
      bsadf,
      lppls: 0,
      sentiment: 0,
      heat: 100,
    }, true);
    expect(mark).toMatch(/stops at 100/);
    expect(mark).not.toMatch(/10413747/);
  });
});

describe("heatClose", () => {
  it("adds the four parts, and says when the score stops at 100", () => {
    expect(heatClose("Stocks", quiet)).toBe(
      "The four parts add to 14.5. Stocks reads Quiet."
    );
    const capped = heatClose("US inflation-linked", {
      residual: 0,
      bsadf: 10413747,
      lppls: 0,
      sentiment: 0,
      heat: 100,
    });
    expect(capped).toMatch(/add to 10,413,747/);
    expect(capped).toMatch(/stops at 100/);
    expect(capped).toMatch(/reads Stretched at 100\.0/);
    expect(capped).not.toMatch(/10413747/);
    expect(capped).not.toMatch(/\u2014/);
    expect(
      heatClose(
        "Cash",
        { residual: 0, bsadf: 0, lppls: 0, sentiment: 0, heat: 0 },
        true
      )
    ).toBe("Cash is held at heat 0, so it stays out of the ranking.");
  });
});

describe("playChangeSentence", () => {
  it("says what changed, what stayed, and how cash is left out", () => {
    expect(
      playChangeSentence({
        name: "Stocks",
        now: { word: "Quiet", heat: 4.4 },
        prev: { word: "Quiet", heat: 15.3 },
        nowDate: "2008-08-22",
        prevDate: "2008-07-23",
      })
    ).toBe(
      "From 23 Jul 2008 to 22 Aug 2008, Stocks went from Quiet at 15.3 to Quiet at 4.4."
    );
    expect(
      playChangeSentence({
        name: "Stocks",
        now: { word: "Quiet", heat: 4.4 },
        prev: { word: "Quiet", heat: 4.4 },
        nowDate: "2008-08-22",
        prevDate: "2008-07-23",
      })
    ).toBe("From 23 Jul 2008 to 22 Aug 2008, Stocks stayed Quiet at 4.4.");
    expect(
      playChangeSentence({
        name: "Stocks",
        now: { word: "Quiet", heat: 2.3 },
        prev: null,
        nowDate: "2008-01-01",
        prevDate: "",
      })
    ).toBe("1 Jan 2008 is the first row for Stocks. It reads Quiet at 2.3.");
    expect(
      playChangeSentence({
        name: "Cash",
        cash: true,
        now: { word: "Quiet", heat: 0 },
        prev: { word: "Quiet", heat: 0 },
        nowDate: "2026-10-02",
        prevDate: "2026-09-03",
      })
    ).toBe("Cash on 2 Oct 2026 is left out and stays at 0.");
  });
});

describe("machinery", () => {
  it("states the weights and the Phillips screen without a dash", () => {
    const text = MACHINERY.join(" ");
    expect(text).toMatch(/12 points per unit/);
    expect(text).toMatch(/stops at 40/);
    expect(text).toMatch(/starts at 25/);
    expect(text).toMatch(/1\.49/);
    expect(text).toMatch(/30 points/);
    expect(text).toMatch(/15 points/);
    expect(text).toMatch(/Phillips, Shi and Yu \(2015\)/);
    expect(text).toMatch(/21 business days/);
    expect(text).not.toMatch(/\u2014/);
    expect(text).not.toMatch(/Sharpe|ERoD/);
  });
});
