import universe from "../data/universe.json";
import { Sleeve } from "./Sleeve";

const STORAGE_KEY = "bc_desk_v1";

export class Portfolio {
  private _weights: Record<string, number> = {};
  private _selectedIndex = 0;

  constructor() {
    this.resetEqual();
  }

  resetEqual(): void {
    const ids = this.sleeveIds;
    const w = ids.length ? 1 / ids.length : 0;
    this._weights = Object.fromEntries(ids.map((id) => [id, w]));
    this._selectedIndex = 0;
  }

  get weights(): Record<string, number> {
    return { ...this._weights };
  }

  get sleeveIds(): string[] {
    return Sleeve.catalog().map((s) => s.def.id);
  }

  get selectedIndex(): number {
    return this._selectedIndex;
  }

  selectPrev(): void {
    const n = this.sleeveIds.length;
    if (n === 0) return;
    this._selectedIndex = (this._selectedIndex - 1 + n) % n;
  }

  selectNext(): void {
    const n = this.sleeveIds.length;
    if (n === 0) return;
    this._selectedIndex = (this._selectedIndex + 1) % n;
  }

  selectIndex(i: number): void {
    const n = this.sleeveIds.length;
    if (n === 0) return;
    this._selectedIndex = ((i % n) + n) % n;
  }

  selectedId(): string {
    return this.sleeveIds[this._selectedIndex] ?? "";
  }

  bumpSelected(delta: number): void {
    const id = this.selectedId();
    if (!id) return;
    this._weights[id] = Math.max(0, (this._weights[id] ?? 0) + delta);
    this.renormalize();
  }

  setWeight(id: string, value: number): void {
    this._weights[id] = Math.max(0, value);
    this.renormalize();
  }

  renormalize(): void {
    const sum = Object.values(this._weights).reduce((a, b) => a + b, 0);
    if (sum <= 0) {
      this.resetEqual();
      return;
    }
    for (const id of Object.keys(this._weights)) {
      this._weights[id] = (this._weights[id] ?? 0) / sum;
    }
  }

  persist(extra: Record<string, unknown> = {}): void {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          v: 1,
          weights: this._weights,
          selectedIndex: this._selectedIndex,
          ...extra,
        })
      );
    } catch {
      /* ignore */
    }
  }

  restore(): Record<string, unknown> | null {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as {
        v?: number;
        weights?: Record<string, number>;
        selectedIndex?: number;
      };
      if (parsed.weights) {
        this._weights = { ...parsed.weights };
        this.renormalize();
      }
      if (typeof parsed.selectedIndex === "number") {
        this._selectedIndex = parsed.selectedIndex;
      }
      return parsed as Record<string, unknown>;
    } catch {
      return null;
    }
  }

  /** Universe metadata for display. */
  static sleeveMeta(id: string) {
    return universe.sleeves.find((s) => s.id === id);
  }
}
