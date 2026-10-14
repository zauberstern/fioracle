/** Real stamps only: dates actually committed. Not a score. */

import { plainDate } from "../../../shared/plainDate";

const KEY = "bc_stamp_album_v1";

export type StampEntry = {
  asOf: string;
  score: number;
  portReturn: number;
};

export function albumDebriefLine(
  entries: StampEntry[],
  limit = 8
): string {
  const slice = entries.slice(-limit);
  if (!slice.length) return "No stamps on this trip yet.";
  return slice
    .map((e) => `${plainDate(e.asOf)} print ${(e.portReturn * 100).toFixed(2)}%`)
    .join(" · ");
}

export class StampAlbum {
  private entries: StampEntry[] = [];

  constructor() {
    this.restore();
  }

  list(): StampEntry[] {
    return [...this.entries];
  }

  count(): number {
    return this.entries.length;
  }

  record(entry: StampEntry): void {
    this.entries.push(entry);
    if (this.entries.length > 64) {
      this.entries = this.entries.slice(-64);
    }
    this.persist();
  }

  /** Debrief line: only dates that were record()ed (signed print). */
  debriefLine(limit = 8): string {
    return albumDebriefLine(this.list(), limit);
  }

  clearSessionSlice(n: number): void {
    /* keep album across sessions; only trim if needed */
    void n;
  }

  private persist(): void {
    try {
      sessionStorage.setItem(KEY, JSON.stringify({ v: 1, entries: this.entries }));
    } catch {
      /* ignore */
    }
  }

  private restore(): void {
    try {
      const raw = sessionStorage.getItem(KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { entries?: StampEntry[] };
      if (Array.isArray(parsed.entries)) this.entries = parsed.entries;
    } catch {
      /* ignore */
    }
  }
}
