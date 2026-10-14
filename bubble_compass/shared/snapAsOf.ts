/** Shared as-of snap: latest tape date at or before the pin (UTC date keys). */

export type LayerRows = Record<string, Array<Record<string, unknown>>>;

export function rowDateKey(row: Record<string, unknown>): string {
  return String(row.as_of ?? "").slice(0, 10);
}

/**
 * Scrubber / episode snap: nearest as_of on the tape at or before target.
 * Returns null when every row is after the pin (no first-row look-ahead).
 * Tip honesty for heat/credit uses rowOnOrBefore in body/src/narrator/heat.ts,
 * which also returns null instead of the first row.
 */
export function snapAsOfIso(layers: LayerRows, dateIso: string): string | null {
  const rows = layers.dlinear ?? layers.bsadf ?? [];
  if (!rows.length) return null;
  const target = dateIso.slice(0, 10);
  let best: string | null = null;
  for (const row of rows) {
    const d = rowDateKey(row);
    if (!d) continue;
    if (d <= target && (best === null || d > best)) best = d;
  }
  return best;
}

/**
 * Index into a sorted ascending asOf frame list using the same <= rule.
 * Returns -1 when no date is on or before the pin (no fallthrough to 0).
 */
export function snapFrameIndex(asOfDates: string[], dateIso: string): number {
  if (!asOfDates.length) return -1;
  const target = dateIso.slice(0, 10);
  let best = -1;
  for (let i = 0; i < asOfDates.length; i++) {
    if (asOfDates[i]! <= target) best = i;
  }
  return best;
}
