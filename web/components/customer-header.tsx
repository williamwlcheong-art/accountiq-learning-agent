import Link from "next/link";

import { LogoutButton } from "@/components/auth/logout-button";

type CustomerHeaderProps = {
  email: string;
  activePage: "wizard" | "account";
};

export function CustomerHeader({ email, activePage }: CustomerHeaderProps) {
  return (
    <nav className="top-nav customer-nav" aria-label="Customer navigation">
      <Link className="nav-brand nav-brand-link" href="/wizard">
        <strong>AccountIQ</strong>
        <span>Financial intelligence</span>
      </Link>
      <div className="customer-nav-links">
        <Link href="/wizard" aria-current={activePage === "wizard" ? "page" : undefined}>
          New valuation
        </Link>
        <Link href="/account" aria-current={activePage === "account" ? "page" : undefined}>
          Account
        </Link>
      </div>
      <div className="nav-user">
        <span className="customer-email">{email}</span>
        <LogoutButton />
      </div>
    </nav>
  );
}
