import "./company-debt.css";

export type DebtGridRow = {
  id: string;
  label: string;
  seriesType: "TRACE" | "OAS" | "CDX" | "OTHER";
  value?: number | null;
  unit?: string;
  asOf?: string;
};

export type CompanyDebtGridProps = {
  rows?: DebtGridRow[];
  title?: string;
};

const TYPE_COLOR: Record<DebtGridRow["seriesType"], string> = {
  TRACE: "#ff6b35",
  OAS: "#e8e8e8",
  CDX: "#e63946",
  OTHER: "#6b6b6b",
};

export function CompanyDebtGrid({ rows = [], title = "Issuer / index debt" }: CompanyDebtGridProps) {
  if (rows.length === 0) {
    return (
      <section className="bc-debt-grid bc-debt-grid--empty" aria-label={title}>
        <h3 className="bc-debt-grid__title">{title}</h3>
        <p className="bc-debt-grid__empty">No issuer fundamentals in catalog</p>
      </section>
    );
  }

  return (
    <section className="bc-debt-grid" aria-label={title}>
      <h3 className="bc-debt-grid__title">{title}</h3>
      <table className="bc-debt-grid__table">
        <thead>
          <tr>
            <th>Series</th>
            <th>Type</th>
            <th>Value</th>
            <th>As of</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.label}</td>
              <td>
                <span
                  className="bc-debt-grid__pill"
                  style={{ borderColor: TYPE_COLOR[row.seriesType] }}
                >
                  {row.seriesType}
                </span>
              </td>
              <td className="bc-debt-grid__mono">
                {row.value != null ? (
                  <>
                    {row.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    {row.unit ? ` ${row.unit}` : ""}
                  </>
                ) : (
                  "-"
                )}
              </td>
              <td className="bc-debt-grid__muted">{row.asOf ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
