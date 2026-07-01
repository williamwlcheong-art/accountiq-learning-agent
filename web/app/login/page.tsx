import Link from "next/link";
import { AuthForm } from "../../components/AuthForm";

export default function LoginPage() {
  return (
    <main className="screen auth-screen">
      <Link className="brand small" href="/">
        <span className="brand-mark">a</span>
        AccountIQ
      </Link>
      <section className="auth-layout">
        <div>
          <p className="eyebrow">Client access</p>
          <h1>Sign in to your report workspace</h1>
          <p className="lede">
            Upload statements, generate a first-draft valuation report, and track review status from one place.
          </p>
        </div>
        <AuthForm />
      </section>
    </main>
  );
}
