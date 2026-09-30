import "./credit.css";

export type BreachCell = {
  quarter: string;
  covenant: string;
  breach_probability: number;
};

export type BreachCalendarProps = {
  quarters?: string[];
  covenants?: string[];
  grid?: number[][];
  cells?: BreachCell[];
  unavailable?: boolean;
  reason?: string | null;
};

function heatColor(p: number): string {
  const t = Math.max(0, Math.min(1, p));
  const r = Math.round(230 + t * 25);
  const g = Math.round(57 * (1 - t));
  const b = Math.round(70 * (1 - t));
  return `rgb(${r},${g},${b})`;
}

export function BreachCalendar({
  quarters = [],
  covenants = [],
  grid = [],
  unavailable = false,
  reason,
}: BreachCalendarProps) {
  const nQ = grid.length;
  const nC = grid[0]?.length ?? 0;

  return (
    <section className="bc-credit bc-credit__panel" aria-label="Breach calendar">
      <h3 className="bc-credit__title">Covenant breach calendar</h3>
      {unavailable || nQ === 0 || nC === 0 ? (
        <p className="bc-credit__empty">{reason ?? "Breach grid unavailable"}</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", color: "#6b6b6b", padding: 4 }} />
              {covenants.map((c) => (
                <th key={c} style={{ color: "#6b6b6b", padding: 4, fontWeight: 500 }}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.map((row, i) => (
              <tr key={quarters[i] ?? i}>
                <td style={{ padding: 4, color: "#ff6b35" }}>{quarters[i]}</td>
                {row.map((p, j) => (
                  <td key={j} style={{ padding: 2 }}>
                    <div
                      title={`${(p * 100).toFixed(0)}%`}
                      style={{
                        height: 22,
                        borderRadius: 3,
                        background: heatColor(p),
                        opacity: 0.85,
                      }}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
