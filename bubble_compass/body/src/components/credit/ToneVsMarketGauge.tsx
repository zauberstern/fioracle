import "./credit.css";

export type ToneVsMarketGaugeProps = {
  value: number | null;
  unavailable?: boolean;
  source?: string | null;
  reason?: string | null;
};

export function ToneVsMarketGauge({
  value,
  unavailable = false,
  source,
  reason,
}: ToneVsMarketGaugeProps) {
  const clamped =
    value === null || unavailable ? 0 : Math.max(-100, Math.min(100, value));
  const pct = ((clamped + 100) / 200) * 100;

  return (
    <section className="bc-credit bc-credit__panel" aria-label="Tone vs market gap">
      <h3 className="bc-credit__title">Tone vs market</h3>
      {unavailable || value === null ? (
        <p className="bc-credit__empty">{reason ?? "Signal unavailable"}</p>
      ) : (
        <>
          <div
            style={{
              position: "relative",
              height: 10,
              borderRadius: 5,
              background: "linear-gradient(90deg, #ff6b35 0%, #333 50%, #e63946 100%)",
            }}
          >
            <div
              style={{
                position: "absolute",
                left: `${pct}%`,
                top: -4,
                width: 4,
                height: 18,
                marginLeft: -2,
                background: "#fff",
                borderRadius: 2,
              }}
            />
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: 8,
              fontSize: 11,
            }}
          >
            <span className="bc-credit__accent">Management optimistic</span>
            <span className="bc-credit__mono">{clamped.toFixed(0)}</span>
            <span className="bc-credit__danger">Market skeptical</span>
          </div>
          {source ? (
            <p className="bc-credit__mono" style={{ marginTop: 6, color: "#6b6b6b" }}>
              {source}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
