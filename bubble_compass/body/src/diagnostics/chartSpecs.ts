/** Pure diagnostic chart specs. No Plotly import. No raw price fields. */

import { READING, PALETTE } from "../../../shared/palette";
import { heatFromTip, statusWord, tipFromLayerRows } from "../narrator/heat";

export const ALLOWED_FIELDS = [
  "residual_z",
  "bsadf_stat",
  "critical_value",
  "bubble_flag",
  "regime_state",
  "boom_probability",
  "bust_probability",
  "lpp_confidence",
  "heat",
] as const;

export const FORBIDDEN_FIELDS = [
  "daily_return",
  "dailyReturn",
  "trend",
  "residual",
  "hy_oas_level_bps",
  "hy_oas_change_20d_bps",
] as const;

export type LayerBundle = Record<string, Array<Record<string, unknown>>>;

export type SleeveDef = {
  id: string;
  label: string;
  color: string;
  cash?: boolean;
};

export type PlotBundle = {
  data: Array<Record<string, unknown>>;
  layout: Record<string, unknown>;
};

export type ChartBuild = {
  heat: PlotBundle;
  residualZ: PlotBundle;
  stretch: PlotBundle;
  regime: PlotBundle;
  prophecy: "empty" | PlotBundle;
  cashStretchNote: boolean;
  /** True when regime_state is the word normal on every row. Odds may still move. */
  regimeWordFlat: boolean;
};

export const REGIME_FLAT_NOTE =
  "The recorded state is normal on every row, including 2020. The chart shows boom and bust probabilities, which do vary. A row may carry a bust probability and remain labelled normal.";

export function assertField(name: string): void {
  if ((FORBIDDEN_FIELDS as readonly string[]).includes(name)) {
    throw new Error(`forbidden field: ${name}`);
  }
}

function baseLayout(title: string): Record<string, unknown> {
  return {
    title: { text: title, font: { family: "IBM Plex Sans, sans-serif", size: 16 } },
    paper_bgcolor: READING.page,
    plot_bgcolor: READING.page,
    font: { family: "IBM Plex Sans, sans-serif", size: 14, color: READING.ink },
    height: 320,
    margin: { t: 48, r: 24, b: 48, l: 56 },
    showlegend: true,
  };
}

function timeLayout(
  title: string,
  xRange?: [string, string],
  pin?: string
): Record<string, unknown> {
  const layout = baseLayout(title);
  return {
    ...layout,
    showlegend: false,
    margin: { t: 12, r: 16, b: 36, l: 44 },
    xaxis: {
      type: "date",
      hoverformat: "%d %b %Y",
      ...(xRange ? { range: xRange, autorange: false } : {}),
    },
    ...(pin
      ? {
          shapes: [
            {
              type: "line",
              xref: "x",
              yref: "paper",
              x0: pin,
              x1: pin,
              y0: 0,
              y1: 1,
              line: { color: "#0072B2", width: 1 },
            },
          ],
        }
      : {}),
  };
}

function asOfOf(row: Record<string, unknown>): string {
  return String(row.as_of ?? "").slice(0, 10);
}

/** Drop every point whose as_of is after the pin (no look-ahead). */
export function rowsOnOrBefore(
  rows: Array<Record<string, unknown>> | undefined,
  asOf: string
): Array<Record<string, unknown>> {
  if (!rows?.length) return [];
  const pin = asOf.slice(0, 10);
  return rows.filter((r) => {
    const d = asOfOf(r);
    return d.length >= 10 && d <= pin;
  });
}

function series(
  rows: Array<Record<string, unknown>>,
  field: string
): { x: string[]; y: number[] } {
  assertField(field);
  const x: string[] = [];
  const y: number[] = [];
  for (const r of rows) {
    const v = r[field];
    if (v == null || !Number.isFinite(Number(v))) continue;
    x.push(asOfOf(r));
    y.push(Number(v));
  }
  return { x, y };
}

export function buildCharts(opts: {
  layersByAsset: Record<string, LayerBundle>;
  selectedId: string;
  asOf: string;
  sleeves: SleeveDef[];
  xRange?: [string, string];
}): ChartBuild {
  const { layersByAsset, selectedId, asOf, sleeves, xRange } = opts;
  const pin = asOf.slice(0, 10);

  const heatLabels: string[] = [];
  const heatVals: number[] = [];
  const heatColors: string[] = [];
  for (const s of sleeves) {
    const layers = layersByAsset[s.id] ?? {};
    const tip = tipFromLayerRows(layers, pin);
    const h = heatFromTip(tip, { cash: Boolean(s.cash) });
    assertField("heat");
    heatLabels.push(s.label);
    heatVals.push(h);
    heatColors.push(s.color);
  }
  const heat: PlotBundle = {
    data: [
      {
        type: "bar",
        orientation: "h",
        y: heatLabels,
        x: heatVals,
        marker: { color: heatColors },
        hovertemplate: "%{y}<br>%{x:.0f}<br>%{customdata}<extra></extra>",
        customdata: heatVals.map((h) => statusWord(h)),
      },
    ],
    layout: {
      ...baseLayout("Heat by book"),
      height: Math.max(360, sleeves.length * 22 + 96),
      margin: { t: 48, r: 24, b: 48, l: 160 },
      xaxis: { range: [0, 100], title: "Heat" },
      yaxis: { autorange: "reversed", automargin: true },
      showlegend: false,
    },
  };

  const selLayers = layersByAsset[selectedId] ?? {};
  const dlinear = rowsOnOrBefore(selLayers.dlinear, pin);
  const bsadf = rowsOnOrBefore(selLayers.bsadf, pin);
  const regimeRows = rowsOnOrBefore(selLayers.regime, pin);
  const lppls = rowsOnOrBefore(selLayers.lppls, pin);

  const rz = series(dlinear, "residual_z");
  const residualZ: PlotBundle = {
    data: [
      {
        type: "scatter",
        mode: "lines",
        name: "Residual",
        x: rz.x,
        y: rz.y,
        line: { color: READING.signal },
      },
    ],
    layout: timeLayout("Standardised residual", xRange, pin),
  };

  const stat = series(bsadf, "bsadf_stat");
  assertField("critical_value");
  assertField("bubble_flag");
  const cvX: string[] = [];
  const cvY: number[] = [];
  const flagX: string[] = [];
  const flagY: number[] = [];
  for (const r of bsadf) {
    const d = asOfOf(r);
    if (r.critical_value != null && Number.isFinite(Number(r.critical_value))) {
      cvX.push(d);
      cvY.push(Number(r.critical_value));
    }
    if (r.bubble_flag === true && r.bsadf_stat != null) {
      flagX.push(d);
      flagY.push(Number(r.bsadf_stat));
    }
  }
  const stretch: PlotBundle = {
    data: [
      {
        type: "scatter",
        mode: "lines",
        name: "Stretch",
        x: stat.x,
        y: stat.y,
        line: { color: READING.signal },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "Critical value",
        x: cvX,
        y: cvY,
        line: { color: PALETTE.vermilion, dash: "dot" },
      },
      {
        type: "scatter",
        mode: "markers",
        name: "Flagged",
        x: flagX,
        y: flagY,
        marker: { color: PALETTE.vermilion, size: 8 },
      },
    ],
    layout: timeLayout("Stretch and critical value", xRange, pin),
  };

  assertField("boom_probability");
  assertField("bust_probability");
  // The published state word is normal on every row, including March 2020.
  // The heuristic keeps that label whenever normal still has the larger share.
  // Boom and bust odds are the series that actually moves.
  const oddsOf = (field: "boom_probability" | "bust_probability") => {
    const x: string[] = [];
    const y: number[] = [];
    for (const r of regimeRows) {
      const v = r[field];
      if (v == null || !Number.isFinite(Number(v))) continue;
      const n = Number(v);
      x.push(asOfOf(r));
      y.push(n <= 1 ? Math.round(n * 100) : Math.round(n));
    }
    return { x, y };
  };
  const boom = oddsOf("boom_probability");
  const bust = oddsOf("bust_probability");
  const stateWords = regimeRows
    .map((r) => String(r.regime_state ?? "").trim())
    .filter((s) => s.length > 0);
  const regimeWordFlat =
    stateWords.length > 0 && stateWords.every((s) => s === "normal");
  const regime: PlotBundle = {
    data: [
      {
        type: "scatter",
        mode: "lines",
        name: "Boom probability",
        x: boom.x,
        y: boom.y,
        line: { color: READING.signal, shape: "hv" },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "Bust probability",
        x: bust.x,
        y: bust.y,
        line: { color: PALETTE.vermilion, shape: "hv" },
      },
    ],
    layout: {
      ...timeLayout("Boom and bust probabilities", xRange, pin),
      yaxis: { title: "Percent", range: [0, 100], zeroline: false },
    },
  };

  const availableLppls = lppls.filter((r) => r.unavailable !== true);
  let prophecy: "empty" | PlotBundle = "empty";
  if (availableLppls.length > 0) {
    const conf = series(availableLppls, "lpp_confidence");
    if (conf.y.length > 0) {
      prophecy = {
        data: [
          {
            type: "scatter",
            mode: "lines",
            name: "lpp_confidence",
            x: conf.x,
            y: conf.y,
            line: { color: READING.signal },
          },
        ],
        layout: baseLayout("Crash-timing confidence"),
      };
    }
  }

  return {
    heat,
    residualZ,
    stretch,
    regime,
    prophecy,
    cashStretchNote: selectedId === "US_CASH_RETURN",
    regimeWordFlat,
  };
}
