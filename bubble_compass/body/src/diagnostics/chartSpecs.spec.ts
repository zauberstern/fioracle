import { describe, expect, it } from "vitest";
import {
  FORBIDDEN_FIELDS,
  assertField,
  buildCharts,
  type LayerBundle,
  type SleeveDef,
} from "./chartSpecs";

const sleeves: SleeveDef[] = [
  { id: "SP500_TOTAL_RETURN", label: "S&P", color: "#4a9eff" },
  { id: "US_CASH_RETURN", label: "Cash", color: "#c8c8c8", cash: true },
];

function layersWithJunk(): LayerBundle {
  return {
    dlinear: [
      {
        as_of: "2008-01-01",
        residual_z: 1,
        daily_return: 99,
        residual: 50,
        trend: 1000,
      },
      {
        as_of: "2008-02-01",
        residual_z: 1.2,
        daily_return: 99,
        residual: 50,
        trend: 1001,
      },
    ],
    bsadf: [
      {
        as_of: "2008-01-01",
        bsadf_stat: 0.5,
        critical_value: 1.49,
        bubble_flag: false,
      },
      {
        as_of: "2008-02-01",
        bsadf_stat: 0.6,
        critical_value: 1.49,
        bubble_flag: false,
      },
    ],
    regime: [
      { as_of: "2008-01-01", regime_state: 0 },
      { as_of: "2008-02-01", regime_state: 0 },
    ],
    lppls: [
      { as_of: "2008-01-01", unavailable: true },
      { as_of: "2008-02-01", unavailable: true },
    ],
    sentiment: [{ as_of: "2008-01-01", unavailable: true }],
  };
}

describe("assertField", () => {
  it("rejects forbidden fields", () => {
    for (const f of FORBIDDEN_FIELDS) {
      expect(() => assertField(f)).toThrow(/forbidden/);
    }
  });

  it("allows residual_z", () => {
    expect(() => assertField("residual_z")).not.toThrow();
  });
});

describe("buildCharts", () => {
  it("never puts daily_return or residual into y arrays", () => {
    const layers = layersWithJunk();
    const built = buildCharts({
      layersByAsset: {
        SP500_TOTAL_RETURN: layers,
        US_CASH_RETURN: layers,
      },
      selectedId: "SP500_TOTAL_RETURN",
      asOf: "2008-02-01",
      sleeves,
    });
    const ys = [
      ...built.residualZ.data,
      ...built.stretch.data,
      ...built.regime.data,
      ...built.heat.data,
    ].flatMap((t) => (Array.isArray(t.y) ? (t.y as number[]) : []));
    expect(ys).not.toContain(99);
    expect(ys).not.toContain(50);
    expect(built.residualZ.data[0]!.y).toContain(1);
  });

  it("cash heat is 0", () => {
    const layers = layersWithJunk();
    const built = buildCharts({
      layersByAsset: {
        SP500_TOTAL_RETURN: layers,
        US_CASH_RETURN: layers,
      },
      selectedId: "US_CASH_RETURN",
      asOf: "2008-02-01",
      sleeves,
    });
    const cashIdx = (built.heat.data[0]!.y as string[]).indexOf("Cash");
    // horizontal bar: y is labels, x is values
    const labels = built.heat.data[0]!.y as string[];
    const vals = built.heat.data[0]!.x as number[];
    const i = labels.indexOf("Cash");
    expect(i).toBeGreaterThanOrEqual(0);
    expect(vals[i]).toBe(0);
    expect(built.cashStretchNote).toBe(true);
    void cashIdx;
  });

  it("unavailable LPPLS yields empty prophecy", () => {
    const layers = layersWithJunk();
    const built = buildCharts({
      layersByAsset: { SP500_TOTAL_RETURN: layers, US_CASH_RETURN: layers },
      selectedId: "SP500_TOTAL_RETURN",
      asOf: "2008-02-01",
      sleeves,
    });
    expect(built.prophecy).toBe("empty");
  });

  it("plots bust odds when the state word stays normal", () => {
    const layers = layersWithJunk();
    layers.regime = [
      {
        as_of: "2020-02-26",
        regime_state: "normal",
        boom_probability: 0,
        bust_probability: 0.3,
      },
      {
        as_of: "2020-03-26",
        regime_state: "normal",
        boom_probability: 0,
        bust_probability: 0.3,
      },
    ];
    const built = buildCharts({
      layersByAsset: { SP500_TOTAL_RETURN: layers, US_CASH_RETURN: layers },
      selectedId: "SP500_TOTAL_RETURN",
      asOf: "2020-03-26",
      sleeves,
    });
    const bust = built.regime.data.find((t) => t.name === "Bust probability");
    const boom = built.regime.data.find((t) => t.name === "Boom probability");
    expect(bust?.y).toEqual([30, 30]);
    expect(boom?.y).toEqual([0, 0]);
    expect(JSON.stringify(built.regime.data)).not.toContain("normal");
    expect(built.regimeWordFlat).toBe(true);
  });

  it("keeps heat category labels inside a wide left margin", () => {
    const production: SleeveDef[] = [
      { id: "SP500_TOTAL_RETURN", label: "Stocks", color: "#171A20" },
      { id: "BBG_US_HIGH_YIELD_TOTAL_RETURN", label: "High yield", color: "#393C41" },
      { id: "BBG_US_CORPORATE_TOTAL_RETURN", label: "Corporates", color: "#5C5E62" },
      { id: "BBG_US_TREASURY_TOTAL_RETURN", label: "Treasuries", color: "#0072B2" },
      { id: "GOLD_TOTAL_RETURN", label: "Gold", color: "#C2410C" },
      { id: "US_CASH_RETURN", label: "Cash", color: "#5C5E62", cash: true },
      {
        id: "CDX_HY_5Y_TOTAL_RETURN",
        label: "High-yield insurance",
        color: "#171A20",
      },
      {
        id: "CDX_IG_5Y_TOTAL_RETURN",
        label: "Investment-grade insurance",
        color: "#0072B2",
      },
    ];
    const layers = layersWithJunk();
    const byId: Record<string, LayerBundle> = {};
    for (const s of production) byId[s.id] = layers;
    const built = buildCharts({
      layersByAsset: byId,
      selectedId: "SP500_TOTAL_RETURN",
      asOf: "2008-02-01",
      sleeves: production,
    });
    const trace = built.heat.data[0]!;
    expect(trace.orientation).toBe("h");
    expect(trace.y).toEqual(production.map((s) => s.label));
    const margin = built.heat.layout.margin as { l: number };
    const yaxis = built.heat.layout.yaxis as { automargin?: boolean };
    expect(margin.l).toBeGreaterThanOrEqual(148);
    expect(yaxis.automargin).toBe(true);
  });

  it("drops points after the pin", () => {
    const layers = layersWithJunk();
    const built = buildCharts({
      layersByAsset: { SP500_TOTAL_RETURN: layers, US_CASH_RETURN: layers },
      selectedId: "SP500_TOTAL_RETURN",
      asOf: "2008-01-01",
      sleeves,
    });
    const x = built.residualZ.data[0]!.x as string[];
    expect(x.every((d) => d <= "2008-01-01")).toBe(true);
    expect(x).not.toContain("2008-02-01");
  });
});
