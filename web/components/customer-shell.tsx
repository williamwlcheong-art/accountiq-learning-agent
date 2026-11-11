import { CustomerHeader, type CustomerPage } from "@/components/customer-header";
import { CONTACT_EMAIL } from "@/lib/site";
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
          <p>Need help? Email <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> and we will sort it out.</p>
        </div>
      </footer>
    </div>
  );
}
