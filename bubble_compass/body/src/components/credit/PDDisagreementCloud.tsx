import "./credit.css";

export type PDPoint = {
  issuer: string;
  model_pd: number;
  market_pd: number;
  exposure: number;
  gap_bps?: number;
};

export type PDDisagreementCloudProps = {
  points?: PDPoint[];
  unavailable?: boolean;
  reason?: string | null;
};

function bubbleRadius(exposure: number, maxExp: number): number {
  if (maxExp <= 0) return 6;
  const t = Math.sqrt(exposure / maxExp);
  return 6 + t * 22;
}

export function PDDisagreementCloud({
  points = [],
  unavailable = false,
  reason,
}: PDDisagreementCloudProps) {
  const w = 280;
  const h = 200;
  const pad = 28;
  const maxPd = Math.max(
    0.01,
    ...points.flatMap((p) => [p.model_pd, p.market_pd]),
  );
  const maxExp = Math.max(1, ...points.map((p) => p.exposure));

  const scale = (pd: number) => pad + (pd / maxPd) * (w - pad * 2);

  return (
    <section className="bc-credit bc-credit__panel" aria-label="PD disagreement">
      <h3 className="bc-credit__title">Model vs market PD</h3>
      {unavailable || points.length === 0 ? (
        <p className="bc-credit__empty">{reason ?? "No issuer PD points"}</p>
      ) : (
        <svg width={w} height={h} role="img">
          <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#333" />
          <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="#333" />
          <line
            x1={pad}
            y1={h - pad}
            x2={w - pad}
            y2={pad}
            stroke="#1f1f1f"
            strokeDasharray="4 4"
          />
          {points.map((p) => {
            const cx = scale(p.market_pd);
            const cy = h - pad - (p.model_pd / maxPd) * (h - pad * 2);
            const r = bubbleRadius(p.exposure, maxExp);
            return (
              <g key={p.issuer}>
                <circle cx={cx} cy={cy} r={r} fill="#ff6b3544" stroke="#ff6b35" />
                <title>
                  {p.issuer}: model {p.model_pd.toFixed(3)}, market {p.market_pd.toFixed(3)}
                </title>
              </g>
            );
          })}
          <text x={w - pad} y={h - 8} fill="#6b6b6b" fontSize={10} textAnchor="end">
            Market PD
          </text>
          <text x={8} y={pad} fill="#6b6b6b" fontSize={10}>
            Model PD
          </text>
        </svg>
      )}
    </section>
  );
}
