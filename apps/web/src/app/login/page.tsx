import { sendMagicLink } from "@/app/login/actions";

export default function LoginPage() {
  return (
    <section className="card">
      <div className="eyebrow">Secure access</div>
      <h1>Customer login</h1>
      <p>
        Enter your email and we will send a magic link. Admin access requires
        the Supabase user to have <code>app_metadata.role = admin</code>.
      </p>
      <form action={sendMagicLink} className="form-grid">
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" name="email" type="email" required />
        </div>
        <button className="button" type="submit">
          Send magic link
        </button>
      </form>
    </section>
  );
}
