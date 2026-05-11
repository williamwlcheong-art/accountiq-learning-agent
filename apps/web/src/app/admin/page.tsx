import { AdminShell } from "@/components/AdminShell";
import { getAdminDashboard } from "@/lib/admin-data";

export default async function AdminPage() {
  const dashboard = await getAdminDashboard();

  return (
    <AdminShell>
      <div className="form-grid">
        <div className="card">
          <div className="eyebrow">Pipeline</div>
          <h1>Lead dashboard</h1>
          <table className="report-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Email</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.leads.map((lead) => (
                <tr key={lead.id}>
                  <td>{lead.company ?? "Unknown"}</td>
                  <td>{lead.email}</td>
                  <td>{lead.status}</td>
                  <td>{lead.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="eyebrow">Uploads</div>
          <h2>Extraction jobs</h2>
          <table className="report-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Status</th>
                <th>Job</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.uploads.map((upload) => (
                <tr key={upload.id}>
                  <td>{upload.original_filename}</td>
                  <td>{upload.extraction_status}</td>
                  <td>{upload.extraction_job_id ?? "Not queued"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="eyebrow">Reports</div>
          <h2>Review and conversion</h2>
          <table className="report-table">
            <thead>
              <tr>
                <th>Report</th>
                <th>Confidence</th>
                <th>Unlocked</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.reports.map((report) => (
                <tr key={report.id}>
                  <td>{report.id}</td>
                  <td>{report.confidence === null ? "Pending" : `${Math.round(report.confidence * 100)}%`}</td>
                  <td>{report.is_unlocked ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AdminShell>
  );
}
