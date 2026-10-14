import { describe, expect, it } from "vitest";
import { heatFromTip, heatParts, rowBefore, rowOnOrBefore, tipFromLayerRows } from "./heat";
import { answerQuestion, type NarratorContext } from "./narrator";

describe("rowOnOrBefore", () => {
  it("returns null when asOf is before every row (no first-row look-ahead)", () => {
    const rows = [
      { as_of: "2020-01-02", residual_z: 0.1 },
      { as_of: "2024-06-03", residual_z: 9.9 },
    ];
    expect(rowOnOrBefore(rows, "2008-01-02")).toBeNull();
  });

  it("returns the latest row on or before asOf", () => {
    const rows = [
      { as_of: "2008-01-01", hy_oas_level_bps: 6 },
      { as_of: "2026-10-02", hy_oas_level_bps: 343 },
    ];
    const hit = rowOnOrBefore(rows, "2008-09-15");
    expect(hit?.hy_oas_level_bps).toBe(6);
  });
});

describe("tipFromLayerRows", () => {
  it("does not look ahead when asOf is before all rows", () => {
    const layers = {
      dlinear: [
        { as_of: "2020-01-02", residual_z: 0.1 },
        { as_of: "2024-06-03", residual_z: 9.9 },
      ],
      bsadf: [
        {
          as_of: "2020-01-02",
          bsadf_stat: 0.5,
          critical_value: 1.49,
          bubble_flag: false,
        },
        {
          as_of: "2024-06-03",
          bsadf_stat: 3,
          critical_value: 1.49,
          bubble_flag: true,
        },
      ],
      lppls: [{ as_of: "2024-06-03", unavailable: true }],
      sentiment: [{ as_of: "2024-06-03", unavailable: true }],
    };
    const tip = tipFromLayerRows(layers, "2008-01-02");
    // No on-or-before row: empty tip, never the first row's residual.
    expect(tip.residualZ).toBe(0);
    expect(tip.bubbleFlag).toBe(false);
  });

  it("marks LPPLS unavailable when the layer is empty", () => {
    const tip = tipFromLayerRows(
      {
        dlinear: [{ as_of: "2024-06-03", residual_z: 1 }],
        bsadf: [
          {
            as_of: "2024-06-03",
            bsadf_stat: 1,
            critical_value: 1.49,
            bubble_flag: false,
          },
        ],
        lppls: [],
        sentiment: [{ as_of: "2024-06-03", unavailable: true }],
      },
      "2024-06-03"
    );
    expect(tip.lpplsUnavailable).toBe(true);
  });
});

describe("heatParts", () => {
  it("splits a quiet unflagged row into residual and stretch points", () => {
    const parts = heatParts({
      residualZ: 1,
      bsadfStat: 0.5,
      criticalValue: 1.49,
      bubbleFlag: false,
      lpplsUnavailable: true,
      sentimentUnavailable: true,
    });
    expect(parts.residual).toBe(12);
    expect(parts.bsadf).toBe(2.5);
    expect(parts.lppls).toBe(0);
    expect(parts.sentiment).toBe(0);
    expect(parts.heat).toBe(14.5);
    expect(heatFromTip({
      residualZ: 1,
      bsadfStat: 0.5,
      criticalValue: 1.49,
      bubbleFlag: false,
      lpplsUnavailable: true,
      sentimentUnavailable: true,
    })).toBe(14.5);
  });

  it("starts the stretch piece at 25 when the flag is on", () => {
    const parts = heatParts({
      residualZ: 0,
      bsadfStat: 2.49,
      criticalValue: 1.49,
      bubbleFlag: true,
      lpplsUnavailable: true,
      sentimentUnavailable: true,
    });
    expect(parts.bsadf).toBe(33);
    expect(parts.heat).toBe(33);
  });

  it("adds crash-timing and headline points only when those layers exist", () => {
    const parts = heatParts({
      residualZ: 0,
      bsadfStat: 0,
      criticalValue: 1.49,
      bubbleFlag: false,
      lpplsUnavailable: false,
      lppConfidence: 0.5,
      sentimentUnavailable: false,
      sentimentVelocity: -2,
    });
    expect(parts.lppls).toBe(15);
    expect(parts.sentiment).toBe(30);
    expect(parts.heat).toBe(45);
  });

  it("cuts the sum off at 100", () => {
    const parts = heatParts({
      residualZ: 10,
      bsadfStat: 4,
      criticalValue: 1.49,
      bubbleFlag: true,
      lpplsUnavailable: false,
      lppConfidence: 1,
      sentimentUnavailable: false,
      sentimentVelocity: 2,
    });
    expect(parts.residual).toBe(40);
    expect(parts.heat).toBe(100);
    expect(parts.residual + parts.bsadf + parts.lppls + parts.sentiment).toBeGreaterThan(100);
  });

  it("forces every piece to 0 for cash", () => {
    const parts = heatParts(
      { residualZ: 4, bubbleFlag: true, bsadfStat: 4, criticalValue: 1.49 },
      { cash: true }
    );
    expect(parts.heat).toBe(0);
    expect(parts.residual).toBe(0);
    expect(parts.bsadf).toBe(0);
  });
});

describe("rowBefore", () => {
  it("returns the row before the on-or-before hit", () => {
    const rows = [
      { as_of: "2008-01-01", residual_z: 1 },
      { as_of: "2008-01-30", residual_z: 2 },
      { as_of: "2008-02-28", residual_z: 3 },
    ];
    expect(rowBefore(rows, "2008-02-01")?.residual_z).toBe(1);
    expect(rowBefore(rows, "2008-01-01")).toBeNull();
  });
});

describe("credit pin", () => {
  it("cites 2008 OAS when asOf is 2008-09-15", () => {
    const ctx: NarratorContext = {
      sleeves: [],
      asOf: "2008-09-15",
      selectedId: "SP500_TOTAL_RETURN",
      regimeState: "normal",
      credit: { hy_oas_level_bps: 6, hy_oas_change_20d_bps: 1, vix: 20 },
    };
    const ans = answerQuestion("credit", ctx);
    const joined = ans.sentences.join(" ");
    expect(joined).toMatch(/one shared series/);
    expect(joined).toMatch(/6/);
    expect(joined).toMatch(/pre-2022 units/);
    expect(joined).not.toMatch(/343/);
  });

  it("heatFromTip cash option is 0", () => {
    expect(
      heatFromTip(
        { residualZ: 9, bubbleFlag: true, bsadfStat: 3 },
        { cash: true }
      )
    ).toBe(0);
  });

  it("frozen OAS tip names shared series, not eight sleeves", () => {
    const ctx: NarratorContext = {
      sleeves: [],
      asOf: "2026-10-02",
      selectedId: "SP500_TOTAL_RETURN",
      regimeState: "normal",
      credit: { hy_oas_level_bps: 343, hy_oas_change_20d_bps: -28, vix: 18 },
    };
    const joined = answerQuestion("credit", ctx).sentences.join(" ");
    expect(joined).toMatch(/one shared series/);
    expect(joined).toMatch(/343 basis points/);
  });
});
