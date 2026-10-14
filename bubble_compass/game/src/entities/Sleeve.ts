import universe from "../data/universe.json";

export type SleeveDef = {
  id: string;
  label: string;
  color: string;
  riskBucket: string;
  spreadBps: number;
  elBps: number;
};

export class Sleeve {
  constructor(readonly def: SleeveDef) {}

  static catalog(): Sleeve[] {
    return universe.sleeves.map((s) => new Sleeve(s as SleeveDef));
  }

  parseColor(): [number, number, number] {
    const h = this.def.color.replace("#", "");
    const r = parseInt(h.slice(0, 2), 16) || 200;
    const g = parseInt(h.slice(2, 4), 16) || 200;
    const b = parseInt(h.slice(4, 6), 16) || 200;
    return [r, g, b];
  }

  chipFrame(index: number): string {
    return `chip_${index % 8}`;
  }
}
