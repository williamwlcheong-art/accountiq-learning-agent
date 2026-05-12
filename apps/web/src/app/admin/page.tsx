import { AdminShell } from "@/components/AdminShell";
import { getAdminDashboard } from "@/lib/admin-data";

function formatDate(value: string) {
  if (value === "Local demo") {
    return value;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-NZ", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function statusClass(status: string) {
  if (["preview_ready", "preview_viewed", "paid"].includes(status)) {
    return "ok";
  }
  if (["failed", "lost", "cancelled"].includes(status)) {
    return "bad";
  }
  return "pending";
}

export default async function AdminPage() {
  const dashboard = await getAdminDashboard();
  const previewReady = dashboard.uploads.filter((upload) => upload.extraction_status === "preview_ready").length;
  const unlockedReports = dashboard.reports.filter((report) => report.is_unlocked).length;

  return (
    <AdminShell>
      <header className="admin-header">
        <div>
          <p className="admin-kicker">Internal dashboard</p>
          <h1>Operations overview</h1>
          <p>Track leads, uploads, preview readiness, and paid unlocks.</p>
        </div>
      </header>

      <section className="admin-stats" aria-label="Admin metrics">
        <div>
          <strong>{dashboard.leads.length}</strong>
          <span>Leads</span>
        </div>
        <div>
          <strong>{dashboard.uploads.length}</strong>
          <span>Uploads</span>
        </div>
        <div>
          <strong>{previewReady}</strong>
          <span>Previews ready</span>
        </div>
        <div>
          <strong>{unlockedReports}</strong>
          <span>Unlocked reports</span>
        </div>
      </section>

      <div className="admin-grid">
        <section className="admin-card admin-card-wide">
          <div className="admin-card-header">
            <div>
              <p className="admin-kicker">Pipeline</p>
              <h2>Lead dashboard</h2>
            </div>
            <span>{dashboard.leads.length} records</span>
          </div>
          <div className="admin-table-wrap">
            <table className="admin-table">
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
                    <td>
                      <span className={`admin-badge ${statusClass(lead.status)}`}>{lead.status}</span>
                    </td>
                    <td>{formatDate(lead.created_at)}</td>
                  </tr>
                ))}
                {dashboard.leads.length === 0 ? (
                  <tr>
                    <td colSpan={4}>No leads found.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="admin-card">
          <div className="admin-card-header">
            <div>
              <p className="admin-kicker">Uploads</p>
              <h2>Extraction jobs</h2>
            </div>
          </div>
          <div className="admin-table-wrap">
            <table className="admin-table">
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
                  <td>
                    <span className={`admin-badge ${statusClass(upload.extraction_status)}`}>
                      {upload.extraction_status}
                    </span>
                  </td>
                  <td>{upload.extraction_job_id ?? "Not queued"}</td>
                </tr>
              ))}
              {dashboard.uploads.length === 0 ? (
                <tr>
                  <td colSpan={3}>No uploads found.</td>
                </tr>
              ) : null}
            </tbody>
            </table>
          </div>
        </section>

        <section className="admin-card">
          <div className="admin-card-header">
            <div>
              <p className="admin-kicker">Reports</p>
              <h2>Review and conversion</h2>
            </div>
          </div>
          <div className="admin-table-wrap">
            <table className="admin-table">
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
                  <td>
                    <span className={`admin-badge ${report.is_unlocked ? "ok" : "pending"}`}>
                      {report.is_unlocked ? "Yes" : "No"}
                    </span>
                  </td>
                </tr>
              ))}
              {dashboard.reports.length === 0 ? (
                <tr>
                  <td colSpan={3}>No reports found.</td>
                </tr>
              ) : null}
            </tbody>
            </table>
          </div>
        </section>
      </div>
    </AdminShell>
  );
}
