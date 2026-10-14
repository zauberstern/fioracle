/** Pure stamp gate: missing prints are not scored turns. */

export type StampPrintDecision =
  | { kind: "no_print" }
  | { kind: "score"; returns: Record<string, number>; benchRet: number };

/**
 * Coerce only finite prints into scoreTurn inputs.
 * Any non-finite sleeve or bench return is a no-print (advance, no score).
 */
export function decideStampPrint(
  sleeveIds: string[],
  rawReturns: Record<string, number>,
  benchRaw: number
): StampPrintDecision {
  const returns: Record<string, number> = {};
  for (const id of sleeveIds) {
    const r = rawReturns[id];
    if (!Number.isFinite(r)) return { kind: "no_print" };
    returns[id] = r as number;
  }
  if (!Number.isFinite(benchRaw)) return { kind: "no_print" };
  return { kind: "score", returns, benchRet: benchRaw };
}
