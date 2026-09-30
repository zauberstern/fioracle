import "./credit.css";

const PILLAR_LABELS: Record<string, string> = {
  liquidity: "Liquidity",
  covenant: "Covenant",
  refinancing: "Refinancing",
  downgrade: "Downgrade",
  legal: "Legal",
};

export type StressLanguageScoreProps = {
  score?: number | null;
  pillars?: Record<string, number>;
  unavailable?: boolean;
  reason?: string | null;
};

export function StressLanguageScore({
  score,
  pillars = {},
  unavailable = false,
  reason,
}: StressLanguageScoreProps) {
  const entries = Object.entries(pillars);

  return (
    <section className="bc-credit bc-credit__panel" aria-label="Stress language">
      <h3 className="bc-credit__title">Distress language intensity</h3>
      {unavailable || score == null || entries.length === 0 ? (
        <p className="bc-credit__empty">{reason ?? "Stress language unavailable"}</p>
      ) : (
        <>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 12 }}>
            <span className="bc-credit__danger" style={{ fontSize: 28, fontWeight: 700 }}>
              {score.toFixed(0)}
            </span>
            <span className="bc-credit__mono" style={{ color: "#6b6b6b" }}>/ 100</span>
          </div>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {entries.map(([key, val]) => (
              <li key={key} style={{ marginBottom: 8 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 11,
                    marginBottom: 4,
                  }}
                >
                  <span>{PILLAR_LABELS[key] ?? key}</span>
                  <span className="bc-credit__mono">{val.toFixed(0)}</span>
                </div>
                <div
                  style={{
                    height: 6,
                    borderRadius: 3,
                    background: "#1f1f1f",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${Math.min(100, val)}%`,
                      height: "100%",
                      background: val >= 60 ? "#e63946" : "#ff6b35",
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
