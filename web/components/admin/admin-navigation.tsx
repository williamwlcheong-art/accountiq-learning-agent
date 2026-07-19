"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/companies", label: "Companies" },
  { href: "/admin/upload", label: "Upload" },
  { href: "/admin/documents", label: "Documents" },
  { href: "/admin/reports", label: "Reports" },
  { href: "/admin/patterns", label: "Patterns" },
  { href: "/admin/financials", label: "Financials" },
  { href: "/admin/wacc-assumptions", label: "WACC assumptions" },
  { href: "/account", label: "Account" },
  { href: "/admin/settings", label: "Settings" },
];

export function AdminNavigation() {
  const pathname = usePathname();

  return (
    <div className="admin-links">
      {links.map((link) => {
        const isDashboard = link.href === "/admin";
        const isActive = isDashboard ? pathname === link.href : pathname === link.href || pathname.startsWith(`${link.href}/`);

        return (
          <Link key={link.href} href={link.href} aria-current={isActive ? "page" : undefined}>
            {link.label}
          </Link>
        );
      })}
    </div>
  );
}
