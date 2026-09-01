import Link from "next/link";

import { ProfileMenu } from "@/components/profile-menu";

export type CustomerPage = "reports" | "wizard" | "account";

type CustomerHeaderProps = {
  email: string;
  isAdmin?: boolean;
  activePage: CustomerPage;
};

const LINKS: Array<{ href: string; label: string; page: CustomerPage }> = [
  { href: "/reports", label: "Your valuations", page: "reports" },
  { href: "/wizard", label: "New valuation", page: "wizard" },
];

export function CustomerHeader({ email, isAdmin = false, activePage }: CustomerHeaderProps) {
  return (
    <header className="portal-header">
      <div className="portal-header-inner">
        <Link className="portal-wordmark" href="/reports">
          AccountIQ
        </Link>
        <nav className="portal-nav" aria-label="Customer navigation">
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href} aria-current={activePage === link.page ? "page" : undefined}>
              {link.label}
            </Link>
          ))}
        </nav>
        <ProfileMenu email={email} isAdmin={isAdmin} />
      </div>
    </header>
  );
}
