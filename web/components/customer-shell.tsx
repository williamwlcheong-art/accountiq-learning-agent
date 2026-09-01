import { CustomerHeader, type CustomerPage } from "@/components/customer-header";
import type { CurrentUser } from "@/types/domain";

type CustomerShellProps = {
  user: CurrentUser;
  activePage: CustomerPage;
  narrow?: boolean;
  children: React.ReactNode;
};

export function CustomerShell({ user, activePage, narrow = false, children }: CustomerShellProps) {
  return (
    <div className="portal">
      <CustomerHeader email={user.email} isAdmin={Boolean(user.is_admin)} activePage={activePage} />
      <main className={narrow ? "portal-main portal-main-narrow" : "portal-main"}>{children}</main>
      <footer className="portal-footer">
        <div className="portal-footer-inner">
          <p>Indicative only. Not financial advice. Every report is reviewed before delivery.</p>
          <p>Need help? Reply to any AccountIQ email and we will sort it out.</p>
        </div>
      </footer>
    </div>
  );
}
