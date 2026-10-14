/** Shared heat 0-100 from tip layer fields (matches marketStore bubbleScoreFromState). */

export type TipLayers = {
  residualZ?: number;
  bsadfStat?: number;
  criticalValue?: number;
  bubbleFlag?: boolean;
  lpplsUnavailable?: boolean;
  lppConfidence?: number;
  sentimentUnavailable?: boolean;
  sentimentVelocity?: number;
};

export type StatusWord = "Quiet" | "Warming" | "Stretched";

export type HeatParts = {
  residual: number;
  bsadf: number;
  lppls: number;
  sentiment: number;
  heat: number;
};

export function statusWord(heat: number): StatusWord {
  if (heat >= 70) return "Stretched";
  if (heat >= 40) return "Warming";
  return "Quiet";
}

export function heatParts(
  t: TipLayers,
  opts?: { cash?: boolean }
): HeatParts {
  // Cash is the sit-still sleeve; never paint it as a bubble heat.
  if (opts?.cash) {
    return { residual: 0, bsadf: 0, lppls: 0, sentiment: 0, heat: 0 };
  }
  const residual = Math.min(40, Math.max(0, t.residualZ ?? 0) * 12);
  const flag = Boolean(t.bubbleFlag);
  const stat = t.bsadfStat ?? 0;
  const cv = t.criticalValue ?? 1.49;
  const bsadf = flag
    ? 25 + Math.max(0, stat - cv) * 8
    : Math.max(0, stat) * 5;
  const lppls = t.lpplsUnavailable
    ? 0
    : (Number.isFinite(t.lppConfidence) ? (t.lppConfidence ?? 0) : 0) * 30;
  const sentiment = t.sentimentUnavailable
    ? 0
    : Math.abs(t.sentimentVelocity ?? 0) * 15;
  const heat = Math.max(0, Math.min(100, residual + bsadf + lppls + sentiment));
  return { residual, bsadf, lppls, sentiment, heat };
}

export function heatFromTip(
  t: TipLayers,
  opts?: { cash?: boolean }
): number {
  return heatParts(t, opts).heat;
}

/**
 * Latest row with as_of <= asOf. Null when every row is after asOf
 * (no look-ahead, no first-row fallthrough).
 * Contrast snapAsOfIso in shared/snapAsOf.ts, which also returns null
 * when the pin is before the series start (no first-row look-ahead).
 */
export function rowOnOrBefore(
  rows: Array<Record<string, unknown>> | undefined,
  asOf: string
): Record<string, unknown> | null {
  if (!rows?.length) return null;
  const pin = asOf.slice(0, 10);
  const hit = [...rows]
    .reverse()
    .find((r) => String(r.as_of ?? "").slice(0, 10) <= pin);
  return hit ?? null;
}

/** The row before the on-or-before hit. Null when the pin is the first row. */
export function rowBefore(
  rows: Array<Record<string, unknown>> | undefined,
  asOf: string
): Record<string, unknown> | null {
  if (!rows?.length) return null;
  const pin = asOf.slice(0, 10);
  const eligible = rows.filter(
    (r) => String(r.as_of ?? "").slice(0, 10) <= pin
  );
  if (eligible.length < 2) return null;
  return eligible[eligible.length - 2] ?? null;
}

export function tipFromLayerRows(
  layers: Record<string, Array<Record<string, unknown>>>,
  asOf?: string
): TipLayers {
  const pick = (name: string): Record<string, unknown> | null => {
    const rows = layers[name];
    if (!rows?.length) return null;
    if (asOf) return rowOnOrBefore(rows, asOf);
    return rows[rows.length - 1] ?? null;
  };
  const d = pick("dlinear") ?? {};
  const b = pick("bsadf") ?? {};
  const lpplsRows = layers.lppls;
  const l = pick("lppls");
  const s = pick("sentiment") ?? {};
  const sentUnavailable =
    s.unavailable === true ||
    (s.sentiment_velocity == null && s.sentimentVelocity == null);
  const lpplsUnavailable =
    !lpplsRows?.length || !l || l.unavailable === true;
  return {
    residualZ: Number(d.residual_z ?? d.residualZ ?? 0),
    bsadfStat: Number(b.bsadf_stat ?? b.bsadfStat ?? 0),
    criticalValue: Number(b.critical_value ?? b.criticalValue ?? 1.49),
    bubbleFlag: Boolean(b.bubble_flag ?? b.bubbleFlag ?? false),
    lpplsUnavailable,
    lppConfidence: Number(l?.lpp_confidence ?? l?.lppConfidence ?? 0),
    sentimentUnavailable: sentUnavailable,
    sentimentVelocity: Number(s.sentiment_velocity ?? s.sentimentVelocity ?? 0),
  };
}
