/**
 * Deterministic eight-question narrator. Templates only; no WebLLM.
 * Sleeve names are plain language. Dates are display dates.
 */

import { bookName } from "../../../shared/books";
import { heatFromTip, tipFromLayerRows, type TipLayers } from "./heat";
import { driverSentence } from "./scoreCopy";
import { plainDate } from "../../../shared/plainDate";

export const CASH_ID = "US_CASH_RETURN";

export const NON_CASH_SLEEVES = [
  "SP500_TOTAL_RETURN",
  "BBG_US_HIGH_YIELD_TOTAL_RETURN",
  "BBG_US_CORPORATE_TOTAL_RETURN",
  "BBG_US_TREASURY_TOTAL_RETURN",
  "GOLD_TOTAL_RETURN",
  "CDX_HY_5Y_TOTAL_RETURN",
  "CDX_IG_5Y_TOTAL_RETURN",
] as const;

export type NarratorQuestionId =
  | "hot"
  | "cracked"
  | "missing"
  | "do"
  | "stretched"
  | "mood"
  | "credit"
  | "age";

export type NarratorQuestion = {
  id: NarratorQuestionId;
  label: string;
};

export const NARRATOR_QUESTIONS: NarratorQuestion[] = [
  { id: "hot", label: "Which book has the highest heat?" },
  { id: "cracked", label: "Where is the fast rise?" },
  { id: "missing", label: "What is missing?" },
  { id: "do", label: "What should I look at?" },
  { id: "stretched", label: "Which books are Stretched?" },
  { id: "mood", label: "What is the market state?" },
  { id: "credit", label: "What do borrowing costs show?" },
  { id: "age", label: "How current is this reading?" },
];

export type SleeveTip = {
  id: string;
  tip: TipLayers;
  asOf: string;
};

export type NarratorContext = {
  sleeves: SleeveTip[];
  asOf: string;
  selectedId: string;
  regimeState: string;
  credit?: {
    hy_oas_level_bps?: number;
    hy_oas_change_20d_bps?: number;
    vix?: number;
  };
  strideDays?: number;
  rowCount?: number;
  historySource?: string;
};

export type NarratorAnswer = {
  sentences: string[];
  citedSleeves: string[];
  refused?: boolean;
};

const REFUSE =
  "That sits outside this reading. Ask what's missing.";

export function sleeveName(id: string): string {
  const name = bookName(id);
  return name;
}

function spreadText(n: number): string {
  const rounded = Math.round(n * 100) / 100;
  if (Math.abs(rounded - Math.round(rounded)) < 1e-9) {
    return String(Math.round(rounded));
  }
  return rounded.toFixed(2);
}

function onDate(asOf: string): string {
  const shown = plainDate(asOf);
  if (!shown || shown === "unknown") return "";
  return ` on ${shown}`;
}

function tipOf(ctx: NarratorContext, id: string): SleeveTip | undefined {
  return ctx.sleeves.find((s) => s.id === id);
}

export function answerQuestion(
  id: NarratorQuestionId,
  ctx: NarratorContext
): NarratorAnswer {
  const asOf = ctx.asOf || "unknown";

  if (id === "hot") {
    const ranked = ctx.sleeves
      .filter((s) => s.id !== CASH_ID)
      .map((s) => ({
        id: s.id,
        tip: s.tip,
        heat: heatFromTip(s.tip),
        z: s.tip.residualZ ?? 0,
        asOf: s.asOf || asOf,
      }))
      .sort((a, b) => b.heat - a.heat || b.z - a.z);
    const top = ranked[0];
    if (!top) {
      return {
        sentences: [
          `No book other than cash is on this history${onDate(asOf)}.`,
        ],
        citedSleeves: [],
      };
    }
    const second = ranked[1];
    const sentences = [
      `${sleeveName(top.id)} has the highest heat, ${top.heat.toFixed(1)}${onDate(top.asOf)}. ${driverSentence(top.tip)}`,
    ];
    if (second) {
      sentences.push(
        `Next is ${sleeveName(second.id)}, at heat ${second.heat.toFixed(1)}${onDate(second.asOf)}. ${driverSentence(second.tip)}`
      );
    }
    sentences.push(
      `Cash is held at heat 0${onDate(asOf)}, so it stays out of this ranking.`
    );
    return {
      sentences: sentences.slice(0, 4),
      citedSleeves: ranked.slice(0, 2).map((r) => r.id),
    };
  }

  if (id === "cracked") {
    const ranked = ctx.sleeves
      .filter((s) => s.id !== CASH_ID)
      .map((s) => ({
        id: s.id,
        gap: (s.tip.bsadfStat ?? 0) - (s.tip.criticalValue ?? 1.49),
        flag: Boolean(s.tip.bubbleFlag),
        stat: s.tip.bsadfStat ?? 0,
        cv: s.tip.criticalValue ?? 1.49,
        asOf: s.asOf || asOf,
      }))
      .sort((a, b) => b.gap - a.gap);
    const top = ranked[0];
    if (!top) {
      return {
        sentences: [`No stretch rows are available${onDate(asOf)}.`],
        citedSleeves: [],
      };
    }
    const sleeve = ctx.sleeves.find((s) => s.id === top.id);
    return {
      sentences: [
        sleeve
          ? `${sleeveName(top.id)}${onDate(top.asOf)}. ${driverSentence(sleeve.tip)}`
          : `No fast-rise row is available${onDate(asOf)}.`,
      ],
      citedSleeves: [top.id],
    };
  }

  if (id === "missing") {
    const sel = tipOf(ctx, ctx.selectedId) ?? ctx.sleeves[0];
    const tip = sel?.tip;
    const sentences: string[] = [];
    if (!tip || tip.lpplsUnavailable) {
      sentences.push(
        `A date for a break is not in this history${onDate(asOf)}, so that part of the score is 0.`
      );
    }
    if (!tip || tip.sentimentUnavailable) {
      sentences.push(
        `News tone is not in this history${onDate(asOf)}, so that part of the score is 0.`
      );
    }
    sentences.push(`Company credit is absent from this history${onDate(asOf)}.`);
    return { sentences: sentences.slice(0, 4), citedSleeves: sel ? [sel.id] : [] };
  }

  if (id === "do") {
    const ranked = ctx.sleeves
      .filter((s) => s.id !== CASH_ID)
      .map((s) => ({ ...s, heat: heatFromTip(s.tip) }))
      .sort((a, b) => b.heat - a.heat);
    const top = ranked[0];
    return {
      sentences: [
        top
          ? `Open ${sleeveName(top.id)} first. Heat is ${top.heat.toFixed(1)}${onDate(top.asOf || asOf)}. ${driverSentence(top.tip)}`
          : `No book other than cash is on this history${onDate(asOf)}.`,
        `No trade is recommended${onDate(asOf)}.`,
        `The next row is ${ctx.strideDays ?? 21} days later${onDate(asOf)}.`,
      ],
      citedSleeves: top ? [top.id] : [],
    };
  }

  if (id === "stretched") {
    const flagged = ctx.sleeves.filter(
      (s) => s.id !== CASH_ID && s.tip.bubbleFlag
    );
    if (!flagged.length) {
      return {
        sentences: [
          `No book other than cash is Stretched${onDate(asOf)}.`,
        ],
        citedSleeves: [],
      };
    }
    const shown = flagged.slice(0, 3);
    const sentences =
      flagged.length === 1
        ? [
            `${sleeveName(shown[0]!.id)} is Stretched${onDate(shown[0]!.asOf || asOf)}. ${driverSentence(shown[0]!.tip)}`,
          ]
        : [
            `${flagged.length} books are Stretched${onDate(asOf)}.`,
            ...shown.map(
              (s) =>
                `${sleeveName(s.id)} is Stretched${onDate(s.asOf || asOf)}. ${driverSentence(s.tip)}`
            ),
          ];
    return {
      sentences: sentences.slice(0, 4),
      citedSleeves: flagged.map((s) => s.id),
    };
  }

  if (id === "mood") {
    const regime = ctx.regimeState || "normal";
    const sel = ctx.selectedId;
    const sleeve = tipOf(ctx, sel);
    const detail = sleeve
      ? `${sleeveName(sel)} heat is ${heatFromTip(sleeve.tip, { cash: sel === CASH_ID }).toFixed(1)}${onDate(sleeve.asOf || asOf)}. ${driverSentence(sleeve.tip)}`
      : `No book row is loaded${onDate(asOf)}.`;
    return {
      sentences: [
        `The market state is ${regime}${onDate(asOf)}.`,
        detail,
      ],
      citedSleeves: [sel],
    };
  }

  if (id === "credit") {
    const c = ctx.credit ?? {};
    const sentences: string[] = [];
    // One shared series: unit jump ~2022-02-01 and a later frozen print.
    const level = c.hy_oas_level_bps;
    const preUnit =
      level != null && Number.isFinite(level) && level > 0 && level < 50;
    const frozen =
      level != null &&
      Number.isFinite(level) &&
      level >= 300 &&
      asOf.slice(0, 10) >= "2022-04-29";
    if (preUnit || frozen) {
      sentences.push(
        `The high-yield spread is one shared series${onDate(asOf)}.`
      );
    }
    if (c.hy_oas_level_bps != null && Number.isFinite(c.hy_oas_level_bps)) {
      sentences.push(
        `The high-yield spread is ${spreadText(c.hy_oas_level_bps)}${preUnit ? " in pre-2022 units, not modern basis points" : " basis points"}${onDate(asOf)}.`
      );
    } else {
      sentences.push(
        `The high-yield spread has no level on this date${onDate(asOf)}.`
      );
    }
    if (
      c.hy_oas_change_20d_bps != null &&
      Number.isFinite(c.hy_oas_change_20d_bps)
    ) {
      sentences.push(
        `Over 20 days, the high-yield spread moved ${spreadText(c.hy_oas_change_20d_bps)} basis points${onDate(asOf)}.`
      );
    }
    if (c.vix != null && Number.isFinite(c.vix)) {
      sentences.push(`VIX is ${c.vix.toFixed(2)}${onDate(asOf)}.`);
    }
    return { sentences: sentences.slice(0, 4), citedSleeves: [] };
  }

  if (id === "age") {
    const sleeve = tipOf(ctx, ctx.selectedId);
    const sentences = [
      `This reading is dated ${plainDate(asOf)}.`,
      `The source is ${ctx.historySource ?? "unknown"}, with a stride of ${ctx.strideDays ?? 21} days and ${ctx.rowCount ?? 0} score rows.`,
    ];
    if (sleeve) {
      sentences.push(
        `${sleeveName(sleeve.id)} heat is ${heatFromTip(sleeve.tip, { cash: sleeve.id === CASH_ID }).toFixed(1)}. ${driverSentence(sleeve.tip)}`
      );
    }
    return {
      sentences,
      citedSleeves: [ctx.selectedId],
    };
  }

  return { sentences: [REFUSE], citedSleeves: [], refused: true };
}

export function refuseOffTopic(): NarratorAnswer {
  return { sentences: [REFUSE], citedSleeves: [], refused: true };
}

export function buildSleeveTip(
  id: string,
  layers: Record<string, Array<Record<string, unknown>>>,
  asOf?: string
): SleeveTip {
  const tip = tipFromLayerRows(layers, asOf);
  const rows = layers.dlinear ?? [];
  const tipAsOf =
    asOf ||
    String(rows[rows.length - 1]?.as_of ?? "").slice(0, 10) ||
    "unknown";
  return { id, tip, asOf: tipAsOf };
}

export { heatFromTip, tipFromLayerRows };
