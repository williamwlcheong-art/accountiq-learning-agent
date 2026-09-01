"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, postForm } from "@/lib/api-client";

type Mode = "login" | "register";

type AuthCardProps = {
  initialMode?: Mode;
};

export function AuthCard({ initialMode = "login" }: AuthCardProps) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showResetHelp, setShowResetHelp] = useState(false);

  function switchMode(nextMode: Mode) {
    setMode(nextMode);
    setError("");
    setPassword("");
    setConfirm("");
    setShowResetHelp(false);
    // Keep the mode in the URL so a refresh or shared link lands on the same form.
    window.history.replaceState(null, "", nextMode === "register" ? "/login?mode=register" : "/login");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail || !password) {
      setError("Email and password are required.");
      return;
    }

    if (mode === "register") {
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (password !== confirm) {
        setError("Passwords do not match.");
        return;
      }
    }

    const formData = new FormData();
    formData.append("email", normalizedEmail);
    formData.append("password", password);

    setLoading(true);
    try {
      await postForm(`/auth/${mode}`, formData);
      router.replace("/");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("An account with this email already exists.");
      } else if (err instanceof ApiError && err.status === 401) {
        setError("Incorrect email or password.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Authentication failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  const isRegister = mode === "register";

  return (
    <section className="auth-card" aria-label="AccountIQ authentication">
      <p className="auth-wordmark" aria-hidden="true">
        AccountIQ
      </p>
      <div className="auth-brand">
        <h1>{isRegister ? "Create your account" : "Sign in"}</h1>
        <p>{isRegister ? "Start your valuation with a secure account." : "Access your valuations and report delivery."}</p>
      </div>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}

      <form onSubmit={submit} className="auth-form">
        <label htmlFor="auth-email">Email address</label>
        <input
          id="auth-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          autoComplete="username"
        />

        <div className="auth-label-row">
          <label htmlFor="auth-password">Password</label>
          {!isRegister ? (
            <button
              type="button"
              className="auth-forgot-link"
              aria-expanded={showResetHelp}
              onClick={() => setShowResetHelp((open) => !open)}
            >
              Forgot password?
            </button>
          ) : null}
        </div>
        <input
          id="auth-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          autoComplete={isRegister ? "new-password" : "current-password"}
          aria-describedby={isRegister ? "auth-password-note" : undefined}
        />
        {isRegister ? (
          <p className="field-note" id="auth-password-note">
            Minimum 8 characters
          </p>
        ) : null}
        {showResetHelp ? (
          <p className="auth-reset-note">
            During early access our team resets passwords manually. Reply to any AccountIQ email you have received and
            we will sort it out for you.
          </p>
        ) : null}

        {isRegister ? (
          <>
            <label htmlFor="auth-confirm">Confirm password</label>
            <input
              id="auth-confirm"
              type="password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              required
              autoComplete="new-password"
            />
          </>
        ) : null}

        <button type="submit" className="button button-primary" disabled={loading}>
          {loading ? (isRegister ? "Creating account..." : "Signing in...") : isRegister ? "Create account" : "Sign in"}
        </button>
      </form>

      <p className="auth-switch">
        {isRegister ? (
          <>
            Already have an account?{" "}
            <button type="button" className="auth-switch-link" onClick={() => switchMode("login")}>
              Sign in
            </button>
          </>
        ) : (
          <>
            New to AccountIQ?{" "}
            <button type="button" className="auth-switch-link" onClick={() => switchMode("register")}>
              Create account
            </button>
          </>
        )}
      </p>

      <Link className="auth-valuation-link" href="/valuation">
        Learn about the valuation advisory
      </Link>
    </section>
  );
}
