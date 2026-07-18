"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, postForm } from "@/lib/api-client";

type Mode = "login" | "register";

export function AuthCard() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function switchMode(nextMode: Mode) {
    setMode(nextMode);
    setError("");
    setPassword("");
    setConfirm("");
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
      <div className="auth-brand">
        <h1>{isRegister ? "Create your AccountIQ account" : "Sign in to AccountIQ"}</h1>
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

        <label htmlFor="auth-password">Password</label>
        <input
          id="auth-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          autoComplete={isRegister ? "new-password" : "current-password"}
        />

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
            <p className="field-note">Minimum 8 characters</p>
          </>
        ) : null}

        <button type="submit" className="button button-primary" disabled={loading}>
          {loading ? "Working..." : isRegister ? "Create account" : "Sign in"}
        </button>
      </form>

      <Link className="auth-valuation-link" href="/valuation">
        Learn about the valuation advisory
      </Link>

      {isRegister ? (
        <button type="button" className="button button-link" onClick={() => switchMode("login")}>
          Sign in instead
        </button>
      ) : (
        <button type="button" className="button button-link" onClick={() => switchMode("register")}>
          Create account
        </button>
      )}
    </section>
  );
}
