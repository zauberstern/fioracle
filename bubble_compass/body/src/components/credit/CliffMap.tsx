import { useMemo, useState } from "react";
import * as Slider from "@radix-ui/react-slider";
import "./credit.css";

export type CliffPoint = {
  issuer: string;
  months_to_wall: number;
  cost_to_ebitda: number;
  debt_outstanding?: number | null;
};

export type CliffMapProps = {
  points?: CliffPoint[];
  unavailable?: boolean;
  reason?: string | null;
  shockCostMultiplier?: number;
};

export function CliffMap({
  points = [],
  unavailable = false,
  reason,
  shockCostMultiplier = 0.15,
}: CliffMapProps) {
  const [yieldShockBps, setYieldShockBps] = useState(0);

  const adjusted = useMemo(
    () =>
      points.map((p) => ({
        ...p,
        cost_to_ebitda:
          p.cost_to_ebitda *
          (1 + shockCostMultiplier * yieldShockBps / 100),
      })),
    [points, yieldShockBps, shockCostMultiplier],
  );

  const w = 280;
  const h = 180;
  const pad = 28;
  const maxMonths = Math.max(1, ...adjusted.map((p) => p.months_to_wall));
  const maxCost = Math.max(0.5, ...adjusted.map((p) => p.cost_to_ebitda));

  return (
    <section className="bc-credit bc-credit__panel" aria-label="Cliff map">
      <h3 className="bc-credit__title">Maturity wall vs leverage</h3>
      {unavailable || points.length === 0 ? (
        <p className="bc-credit__empty">{reason ?? "Cliff map unavailable"}</p>
      ) : (
        <>
          <label className="bc-credit__mono" style={{ display: "block", marginBottom: 8 }}>
            Yield shock: {yieldShockBps} bps
          </label>
          <Slider.Root
            className="bc-cliff-slider"
            min={0}
            max={400}
            step={25}
            value={[yieldShockBps]}
            onValueChange={(v) => setYieldShockBps(v[0] ?? 0)}
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              height: 20,
              marginBottom: 12,
            }}
          >
            <Slider.Track
              style={{ flex: 1, height: 4, background: "#1f1f1f", borderRadius: 2 }}
            >
              <Slider.Range style={{ height: "100%", background: "#ff6b35" }} />
            </Slider.Track>
            <Slider.Thumb
              style={{
                width: 14,
                height: 14,
                background: "#e63946",
                borderRadius: "50%",
              }}
            />
          </Slider.Root>
          <svg width={w} height={h}>
            {adjusted.map((p) => {
              const x = pad + (p.months_to_wall / maxMonths) * (w - pad * 2);
              const y = h - pad - (p.cost_to_ebitda / maxCost) * (h - pad * 2);
              return (
                <g key={p.issuer}>
                  <circle cx={x} cy={y} r={5} fill="#ff6b35" />
                  <text x={x + 6} y={y - 4} fill="#e8e8e8" fontSize={10}>
                    {p.issuer}
                  </text>
                </g>
              );
            })}
            <text x={w - pad} y={h - 6} fill="#6b6b6b" fontSize={10} textAnchor="end">
              Months to wall
            </text>
          </svg>
        </>
      )}
    </section>
  );
}
