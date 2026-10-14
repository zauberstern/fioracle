/** Banked Book pack: largest-remainder integers that sum to 100. */

export function weightsToQty(
  weights: Record<string, number>,
  ids: readonly string[]
): Record<string, number> {
  const raw = ids.map((id) => {
    const w = Number(weights[id] ?? 0);
    return Number.isFinite(w) && w > 0 ? w : 0;
  });
  const sum = raw.reduce((a, b) => a + b, 0);
  if (sum <= 0) {
    const out: Record<string, number> = {};
    for (const id of ids) out[id] = 0;
    const cash = ids.includes("US_CASH_RETURN")
      ? "US_CASH_RETURN"
      : ids[ids.length - 1];
    if (cash) out[cash] = 100;
    return out;
  }
  const scaled = raw.map((w) => (w / sum) * 100);
  const floors = scaled.map((v) => Math.floor(v));
  let rem = 100 - floors.reduce((a, b) => a + b, 0);
  const order = scaled
    .map((v, i) => ({ i, frac: v - floors[i] }))
    .sort((a, b) => b.frac - a.frac);
  for (let k = 0; k < rem; k++) {
    floors[order[k % order.length].i] += 1;
  }
  const out: Record<string, number> = {};
  ids.forEach((id, i) => {
    out[id] = floors[i];
  });
  return out;
}

export type PackSlot = {
  id: string;
  short: string;
  qty: number;
  selected: boolean;
};
