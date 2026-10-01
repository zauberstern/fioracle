import { Sleeve } from "./Sleeve";

export class Portfolio {
  private _weights: Record<string, number> = {};
  private _selectedIndex = 0;

  constructor() {
    this.reset();
  }

  reset(): void {
    const sleeves = Sleeve.catalog();
    const n = sleeves.length;
    const even = n > 0 ? 1 / n : 0;
    this._weights = {};
    this._selectedIndex = 0;
    for (const s of sleeves) {
      this._weights[s.def.id] = even;
    }
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

  selectNext(): void {
    const n = this.sleeveIds.length;
    if (n === 0) return;
    this._selectedIndex = (this._selectedIndex + 1) % n;
  }

  selectPrev(): void {
    const n = this.sleeveIds.length;
    if (n === 0) return;
    this._selectedIndex = (this._selectedIndex - 1 + n) % n;
  }

  selectedId(): string {
    return this.sleeveIds[this._selectedIndex] ?? "";
  }

  bumpSelected(delta: number): void {
    const id = this.selectedId();
    if (!id) return;
    const next = Math.max(0, Math.min(1, (this._weights[id] ?? 0) + delta));
    this._weights[id] = next;
    this.renormalize();
  }

  private renormalize(): void {
    const sum = Object.values(this._weights).reduce((a, b) => a + b, 0);
    if (sum <= 0) return;
    for (const id of Object.keys(this._weights)) {
      this._weights[id] /= sum;
    }
  }
}
