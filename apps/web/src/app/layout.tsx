import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AccountIQ | Financial statement analysis",
  description:
    "Upload financial statements and get a structured preview of the numbers that matter.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en-NZ">
      <body>
        <main className="page-shell">
          <nav className="nav" aria-label="Main navigation">
            <Link href="/" className="brand">
              AccountIQ
              <span>Learning Agent</span>
            </Link>
            <div className="nav-links">
              <Link href="/upload">Upload</Link>
              <Link href="/admin">Admin</Link>
              <Link href="/login" className="pill">
                Log in
              </Link>
            </div>
          </nav>
          {children}
        </main>
      </body>
    </html>
  );
}
