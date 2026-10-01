import universe from "../data/universe.json";

export interface SleeveDef {
  id: string;
  label: string;
  color: string;
  riskBucket: string;
  spreadBps: number;
  elBps: number;
}

export class Sleeve {
  readonly def: SleeveDef;

  constructor(def: SleeveDef) {
    this.def = def;
  }

  static catalog(): Sleeve[] {
    return universe.sleeves.map((s) => new Sleeve(s as SleeveDef));
  }

  parseColor(): [number, number, number] {
    const hex = this.def.color.replace("#", "");
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return [r, g, b];
  }
}
