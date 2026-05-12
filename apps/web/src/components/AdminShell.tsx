import Link from "next/link";

export function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <section className="admin-shell">
      <aside className="admin-sidebar">
        <div>
          <div className="admin-brand">AccountIQ</div>
          <p className="admin-muted">Learning Agent</p>
        </div>
        <nav className="admin-menu" aria-label="Admin navigation">
          <Link href="/admin">Dashboard</Link>
          <Link href="/upload">Upload flow</Link>
          <Link href="/preview/demo">Sample report</Link>
        </nav>
        <div className="admin-note">
          <strong>Internal console</strong>
          <span>Lead capture, extraction jobs, reports, and conversion checks.</span>
        </div>
      </aside>
      <div className="admin-main">{children}</div>
    </section>
  );
}
