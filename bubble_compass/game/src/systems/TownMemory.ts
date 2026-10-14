/** Visit / stone tour memory. Not a score field. */

const KEY = "bc_town_v1";

export type TownMemoryState = {
  v: 1;
  visits: Record<string, number>;
  stones: string[];
};

export class TownMemory {
  private visits: Record<string, number> = {};
  private stones = new Set<string>();
  private lastDistrict: string | null = null;

  constructor() {
    this.restore();
  }

  visitCount(sleeveId: string): number {
    return this.visits[sleeveId] ?? 0;
  }

  /** Edge-triggered: increment once when entering a district cell. */
  enterDistrict(sleeveId: string | null): number {
    if (!sleeveId) {
      this.lastDistrict = null;
      return 0;
    }
    if (this.lastDistrict === sleeveId) return this.visitCount(sleeveId);
    this.lastDistrict = sleeveId;
    const next = (this.visits[sleeveId] ?? 0) + 1;
    this.visits[sleeveId] = next;
    this.persist();
    return next;
  }

  touchStone(dateIso: string): void {
    const d = dateIso.slice(0, 10);
    if (!d) return;
    this.stones.add(d);
    this.persist();
  }

  stoneCount(): number {
    return this.stones.size;
  }

  tourComplete(requiredDates: string[]): boolean {
    if (!requiredDates.length) return false;
    return requiredDates.every((d) => this.stones.has(d.slice(0, 10)));
  }

  tourLine(requiredDates: string[]): string | null {
    if (!this.tourComplete(requiredDates)) return null;
    return "You have touched every flood stone. Those dates are the public ones.";
  }

  /** Brass outline tiers: none, after 3, after 9. */
  outlineTier(sleeveId: string): 0 | 1 | 2 {
    const n = this.visitCount(sleeveId);
    if (n >= 9) return 2;
    if (n >= 3) return 1;
    return 0;
  }

  private persist(): void {
    try {
      const payload: TownMemoryState = {
        v: 1,
        visits: { ...this.visits },
        stones: [...this.stones],
      };
      sessionStorage.setItem(KEY, JSON.stringify(payload));
    } catch {
      /* ignore */
    }
  }

  private restore(): void {
    try {
      const raw = sessionStorage.getItem(KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as TownMemoryState;
      if (parsed?.v !== 1) return;
      if (parsed.visits && typeof parsed.visits === "object") {
        this.visits = { ...parsed.visits };
      }
      if (Array.isArray(parsed.stones)) {
        this.stones = new Set(parsed.stones.map((s) => String(s).slice(0, 10)));
      }
    } catch {
      /* ignore */
    }
  }
}
