import Link from "next/link";

export function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <section className="upload-panel">
      <aside className="card">
        <div className="eyebrow">Internal</div>
        <h2>Admin</h2>
        <p>Track leads, uploads, preview status, and payment conversion.</p>
        <div className="form-grid">
          <Link href="/admin">Dashboard</Link>
          <Link href="/upload">Upload flow</Link>
          <Link href="/preview/demo">Sample report</Link>
        </div>
      </aside>
      <div>{children}</div>
    </section>
  );
}
