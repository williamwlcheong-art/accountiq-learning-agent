"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../lib/api";

type AuthMode = "login" | "register";

export function AuthForm() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");

    const body = new FormData();
    body.append("email", email);
    body.append("password", password);

    try {
      await apiFetch<{ id: number; email: string }>(`/auth/${mode}`, {
        method: "POST",
        body,
      });
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-panel" onSubmit={submit}>
      <div className="segmented" aria-label="Authentication mode">
        <button
          className={mode === "login" ? "active" : ""}
          type="button"
          onClick={() => setMode("login")}
        >
          Sign in
        </button>
        <button
          className={mode === "register" ? "active" : ""}
          type="button"
          onClick={() => setMode("register")}
        >
          Create account
        </button>
      </div>

      <label>
        Email
        <input
          autoComplete="email"
          inputMode="email"
          onChange={(event) => setEmail(event.target.value)}
          required
          type="email"
          value={email}
        />
      </label>
      <label>
        Password
        <input
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          minLength={8}
          onChange={(event) => setPassword(event.target.value)}
          required
          type="password"
          value={password}
        />
      </label>

      {error ? <p className="form-error">{error}</p> : null}

      <button className="primary-button full-width" disabled={busy} type="submit">
        <LockKeyhole aria-hidden="true" size={18} />
        {busy ? "Working" : mode === "login" ? "Sign in" : "Create account"}
        <ArrowRight aria-hidden="true" size={18} />
      </button>
    </form>
  );
}
