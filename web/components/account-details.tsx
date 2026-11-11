import { formatNzDate } from "@/lib/presentation";
import { CONTACT_EMAIL } from "@/lib/site";
import type { CurrentUser } from "@/types/domain";

type AccountDetailsProps = {
  user: CurrentUser;
};

export function AccountDetails({ user }: AccountDetailsProps) {
  return (
    <section className="panel" aria-labelledby="account-details-heading">
      <h2 id="account-details-heading">Details</h2>
      <dl className="detail-list">
        <div>
          <dt>Email address</dt>
          <dd>{user.email}</dd>
        </div>
        <div>
          <dt>Member since</dt>
          <dd>{formatNzDate(user.created_at, "long")}</dd>
        </div>
        <div>
          <dt>Password</dt>
          <dd>
            During early access our team changes passwords for you. Email <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> and we will sort it out.
          </dd>
        </div>
      </dl>
    </section>
  );
}
