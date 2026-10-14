/** Display dates. Storage and snaps stay ISO (YYYY-MM-DD). */

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

/** "2026-10-02" -> "2 Oct 2026". Non-dates pass through. */
export function plainDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso.trim());
  if (!m) return iso;
  const month = MONTHS[Number(m[2]) - 1];
  const day = Number(m[3]);
  if (!month || !day) return iso;
  return `${day} ${month} ${m[1]}`;
}
