import { describe, expect, it } from "vitest";
import {
  CASH_ID,
  answerQuestion,
  buildSleeveTip,
  refuseOffTopic,
  type NarratorContext,
} from "./narrator";

function layers(opts: {
  z?: number;
  flag?: boolean;
  lpplsUnavailable?: boolean;
  sentimentUnavailable?: boolean;
  asOf?: string;
}): Record<string, Array<Record<string, unknown>>> {
  const asOf = opts.asOf ?? "2024-06-03";
  return {
    dlinear: [{ as_of: asOf, residual_z: opts.z ?? 1.2 }],
    bsadf: [
      {
        as_of: asOf,
        bsadf_stat: opts.flag ? 2.5 : 0.8,
        critical_value: 1.49,
        bubble_flag: Boolean(opts.flag),
      },
    ],
    lppls: [
      {
        as_of: asOf,
        unavailable: opts.lpplsUnavailable ?? true,
        lpp_confidence: 0,
      },
    ],
    sentiment: [
      {
        as_of: asOf,
        unavailable: opts.sentimentUnavailable ?? true,
      },
    ],
    regime: [{ as_of: asOf, regime_state: "normal" }],
  };
}

function ctx(partial?: Partial<NarratorContext>): NarratorContext {
  const sleeves = [
    buildSleeveTip("SP500_TOTAL_RETURN", layers({ z: 2.0, flag: true })),
    buildSleeveTip(
      "BBG_US_HIGH_YIELD_TOTAL_RETURN",
      layers({ z: 0.5, flag: false })
    ),
    buildSleeveTip(CASH_ID, layers({ z: 9.0, flag: true })),
  ];
  return {
    sleeves,
    asOf: "2024-06-03",
    selectedId: "SP500_TOTAL_RETURN",
    regimeState: "normal",
    credit: { hy_oas_level_bps: 350, hy_oas_change_20d_bps: 12, vix: 18 },
    strideDays: 21,
    rowCount: 40,
    historySource: "static",
    ...partial,
  };
}

describe("narrator", () => {
  it("does not rank cash as hot", () => {
    const ans = answerQuestion("hot", ctx());
    expect(ans.sentences.join(" ")).toMatch(/held at heat 0/);
    expect(ans.sentences.join(" ")).toMatch(/2\.00 steps above/);
    expect(ans.sentences.join(" ")).toMatch(/fast-rise reading is 2\.50/);
    expect(ans.citedSleeves).not.toContain(CASH_ID);
    expect(ans.citedSleeves[0]).toBe("SP500_TOTAL_RETURN");
    expect(ans.sentences.join(" ")).toContain("Stocks");
    expect(ans.sentences.join(" ")).not.toMatch(/TOTAL_RETURN|`/);
  });

  it("unavailable LPPLS does not invent a rift date", () => {
    const ans = answerQuestion("missing", ctx());
    expect(ans.sentences.join(" ")).toMatch(/date for a break is not in this history/);
    expect(ans.sentences.join(" ")).not.toMatch(/\d{4}-\d{2}-\d{2} to \d{4}/);
    expect(ans.sentences.join(" ")).not.toMatch(/TOTAL_RETURN|`/);
  });

  it("each answer carries a citation", () => {
    for (const id of [
      "hot",
      "cracked",
      "missing",
      "do",
      "stretched",
      "mood",
      "credit",
      "age",
    ] as const) {
      const ans = answerQuestion(id, ctx());
      expect(ans.sentences.length).toBeGreaterThan(0);
      expect(ans.sentences.length).toBeLessThanOrEqual(4);
      expect(ans.sentences.join(" ")).not.toMatch(/TOTAL_RETURN|`/);
    }
  });

  it("names a flagged sleeve without the raw identifier", () => {
    const ans = answerQuestion("stretched", ctx());
    const text = ans.sentences.join(" ");
    expect(text).toContain("Stocks is Stretched");
    expect(text).toContain("3 Jun 2024");
    expect(text).not.toMatch(/TOTAL_RETURN|bubble_flag|`/);
  });

  it("refuses off-topic scandal prompts in one fixed sentence", () => {
    const ans = refuseOffTopic();
    expect(ans.refused).toBe(true);
    expect(ans.sentences).toHaveLength(1);
  });
});
