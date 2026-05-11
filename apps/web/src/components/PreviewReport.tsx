import type { PreviewReportData } from "@/types/report";

const currencyFormatter = new Intl.NumberFormat("en-NZ", {
  currency: "NZD",
  maximumFractionDigits: 0,
  style: "currency",
});

export function PreviewReport({ report }: { report: PreviewReportData }) {
  return (
    <section className="card">
      <div className="eyebrow">Partial preview</div>
      <h1>{report.companyName}</h1>
      <p>{report.summary}</p>
      <div className="metric-grid">
        <div className="metric">
          <strong>{Math.round(report.confidence * 100)}%</strong>
          <p>Extraction confidence</p>
        </div>
        <div className="metric">
          <strong>{report.rows.length}</strong>
          <p>Rows shown before unlock</p>
        </div>
        <div className="metric">
          <strong>{report.lockedSections.length}</strong>
          <p>Locked report sections</p>
        </div>
      </div>
      <table className="report-table">
        <thead>
          <tr>
            <th>Statement</th>
            <th>Row</th>
            <th>Period</th>
            <th>Value</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {report.rows.map((row) => (
            <tr key={`${row.statement}-${row.label}-${row.period}`}>
              <td>{row.statement.toUpperCase()}</td>
              <td>{row.label}</td>
              <td>{row.period}</td>
              <td>{row.value === null ? "Not found" : currencyFormatter.format(row.value)}</td>
              <td>{Math.round(row.confidence * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
