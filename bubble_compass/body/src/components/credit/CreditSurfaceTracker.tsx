import "./credit.css";

export type CreditSurfaceTrackerProps = {
  spreadBps?: number[];
  ltv?: number[];
  steepeningFlag?: boolean;
  slopeBpsPerLtv?: number | null;
  unavailable?: boolean;
  reason?: string | null;
};

export function CreditSurfaceTracker({
  spreadBps = [],
  ltv = [],
  steepeningFlag = false,
  slopeBpsPerLtv,
  unavailable = false,
  reason,
}: CreditSurfaceTrackerProps) {
  const w = 280;
  const h = 140;
  const pad = 24;
  const n = Math.min(spreadBps.length, ltv.length);

  const maxSpread = Math.max(1, ...spreadBps.slice(0, n));
  const maxLtv = Math.max(0.01, ...ltv.slice(0, n));

  return (
    <section className="bc-credit bc-credit__panel" aria-label="Credit surface">
      <h3 className="bc-credit__title">Spread vs LTV surface</h3>
      {unavailable || n < 2 ? (
        <p className="bc-credit__empty">{reason ?? "Surface series unavailable"}</p>
      ) : (
        <>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
            <span
              className={steepeningFlag ? "bc-credit__danger" : "bc-credit__accent"}
              style={{ fontSize: 12, fontWeight: 600 }}
            >
              {steepeningFlag ? "Steepening" : "Stable"}
            </span>
            {slopeBpsPerLtv != null ? (
              <span className="bc-credit__mono" style={{ color: "#6b6b6b" }}>
                slope {slopeBpsPerLtv.toFixed(2)} bps/LTV
              </span>
            ) : null}
          </div>
          <svg width={w} height={h}>
            <polyline
              fill="none"
              stroke="#ff6b35"
              strokeWidth={2}
              points={spreadBps
                .slice(0, n)
                .map((s, i) => {
                  const x = pad + (ltv[i] / maxLtv) * (w - pad * 2);
                  const y = h - pad - (s / maxSpread) * (h - pad * 2);
                  return `${x},${y}`;
                })
                .join(" ")}
            />
            {spreadBps.slice(0, n).map((s, i) => {
              const x = pad + (ltv[i] / maxLtv) * (w - pad * 2);
              const y = h - pad - (s / maxSpread) * (h - pad * 2);
              return <circle key={i} cx={x} cy={y} r={3} fill="#e63946" />;
            })}
          </svg>
        </>
      )}
    </section>
  );
}
