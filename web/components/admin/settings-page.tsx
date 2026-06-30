"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch, postForm } from "@/lib/api-client";

type Settings = {
  api_key_set: boolean;
  api_key_preview: string;
  claude_model: string;
};

export function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function loadSettings() {
    try {
      setSettings(await apiFetch<Settings>("/settings"));
      setError("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Settings failed to load.");
    }
  }

  useEffect(() => {
    let cancelled = false;
    apiFetch<Settings>("/settings")
      .then((nextSettings) => {
        if (cancelled) return;
        setSettings(nextSettings);
        setError("");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        if (!cancelled) setError(err instanceof Error ? err.message : "Settings failed to load.");
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const form = new FormData(formElement);
      const apiKey = String(form.get("api_key") ?? "").trim();
      if (!apiKey) form.delete("api_key");
      const response = await postForm<{ ok: boolean; message: string }>("/settings", form);
      setMessage(response.message);
      await loadSettings();
      formElement.reset();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Settings could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="admin-page">
      <header className="page-header">
        <h1>Settings</h1>
      </header>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
        </div>
      ) : null}
      {message ? <div className="alert alert-success">{message}</div> : null}

      <form className="panel admin-form" onSubmit={save}>
        <p className="muted">
          API key status: {settings?.api_key_set ? `configured (${settings.api_key_preview})` : "not configured"}
        </p>
        <label htmlFor="api-key">
          API Key
          <input id="api-key" name="api_key" type="password" placeholder="sk-ant-..." autoComplete="off" />
        </label>
        <label htmlFor="claude-model">
          Claude Model
          <select id="claude-model" name="claude_model" defaultValue={settings?.claude_model || "claude-sonnet-4-6"}>
            <option value="claude-sonnet-4-6">claude-sonnet-4-6</option>
            <option value="claude-opus-4-7">claude-opus-4-7</option>
            <option value="claude-haiku-4-5-20251001">claude-haiku-4-5</option>
          </select>
        </label>
        <button className="button button-primary" disabled={saving}>
          {saving ? "Saving..." : "Save & Apply"}
        </button>
      </form>
    </section>
  );
}
