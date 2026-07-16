"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch, postForm } from "@/lib/api-client";

type Settings = {
  demo_mode: boolean;
  demo_mode_configured?: boolean;
  demo_mode_forced?: boolean;
  api_key_set: boolean;
  api_key_preview: string;
  claude_model: string;
};

type AiConnectionCheck = {
  ok: boolean;
  status: "demo_mode" | "missing_key" | "verified" | "failed" | string;
  message: string;
  model: string;
  demo_mode: boolean;
  api_key_set: boolean;
  cached?: boolean;
};

export function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [claudeModel, setClaudeModel] = useState("claude-sonnet-4-6");
  const [demoMode, setDemoMode] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [checkingConnection, setCheckingConnection] = useState(false);
  const [connectionCheck, setConnectionCheck] = useState<AiConnectionCheck | null>(null);

  async function loadSettings() {
    try {
      const nextSettings = await apiFetch<Settings>("/settings");
      setSettings(nextSettings);
      setClaudeModel(nextSettings.claude_model || "claude-sonnet-4-6");
      setDemoMode(nextSettings.demo_mode);
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
        setClaudeModel(nextSettings.claude_model || "claude-sonnet-4-6");
        setDemoMode(nextSettings.demo_mode);
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
      form.set("demo_mode", demoMode ? "true" : "false");
      const response = await postForm<{ ok: boolean; message: string }>("/settings", form);
      setMessage(response.message);
      setConnectionCheck(null);
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

  async function verifyConnection() {
    setCheckingConnection(true);
    setError("");
    setMessage("");
    setConnectionCheck(null);
    try {
      const response = await apiFetch<AiConnectionCheck>("/settings/ai-connection/check", {
        method: "POST",
      });
      setConnectionCheck(response);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "AI connection could not be checked.");
    } finally {
      setCheckingConnection(false);
    }
  }

  const connectionAlertClass =
    connectionCheck?.status === "demo_mode"
      ? "alert alert-info"
      : connectionCheck?.ok
        ? "alert alert-success"
        : "alert alert-error";
  const liveConnectionUnavailable = settings && !settings.demo_mode && !settings.api_key_set;

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

      {settings?.demo_mode ? (
        <div className="alert alert-info">
          <div>
            <strong>Demo mode is active — no API key is required.</strong>
            <p>
              You can test uploads, the five-question valuation journey and PDF delivery. Company
              research and report content use deterministic sample data rather than live online research.
            </p>
          </div>
        </div>
      ) : null}
      {liveConnectionUnavailable ? (
        <div className="alert alert-warning">
          <div>
            <strong>Live report generation is not configured yet.</strong>
            <p>
              Without demo mode or a verified Anthropic API key, customers cannot generate live
              valuation reports. Enable demo mode for local testing, or add and verify a live key
              before turning this on for customers.
            </p>
          </div>
        </div>
      ) : null}

      <form className="panel admin-form" onSubmit={save}>
        <div>
          <h2>Demo mode and live research</h2>
          <p className="muted">
            Use demo mode to keep testing the five-question valuation journey, sample extraction and
            PDF delivery without an Anthropic key. Turn it off when you are ready to use live research.
          </p>
        </div>
        <label className="checkbox-row" htmlFor="demo-mode">
          <input
            id="demo-mode"
            name="demo_mode_toggle"
            type="checkbox"
            checked={demoMode}
            onChange={(event) => setDemoMode(event.target.checked)}
          />
          <span>
            Enable demo mode
            {settings?.demo_mode_forced ? (
              <small className="muted"> Test mode is also forcing demo behaviour for this session.</small>
            ) : (
              <small className="muted"> Reports will be clearly labelled as simulated and not for reliance.</small>
            )}
          </span>
        </label>
        <p className="muted">
          Live API key: {settings?.api_key_set ? `configured (${settings.api_key_preview})` : "not configured"}
        </p>
        {connectionCheck ? (
          <div className={connectionAlertClass}>
            <strong>
              {connectionCheck.status === "verified"
                ? "Live AI connection verified"
                : connectionCheck.status === "demo_mode"
                  ? "Demo mode active"
                  : "Live AI connection not verified"}
            </strong>
            <p>{connectionCheck.message}</p>
            <p className="muted">
              Model: {connectionCheck.model}
              {connectionCheck.cached ? " — recently verified" : ""}
            </p>
          </div>
        ) : null}
        <label htmlFor="api-key">
          Anthropic API key <span className="optional-label">Optional</span>
          <input id="api-key" name="api_key" type="password" placeholder="sk-ant-..." autoComplete="off" />
        </label>
        <label htmlFor="claude-model">
          Claude Model
          <select
            id="claude-model"
            name="claude_model"
            value={claudeModel}
            onChange={(event) => setClaudeModel(event.target.value)}
          >
            <option value="claude-sonnet-4-6">claude-sonnet-4-6</option>
            <option value="claude-opus-4-7">claude-opus-4-7</option>
            <option value="claude-haiku-4-5-20251001">claude-haiku-4-5</option>
          </select>
        </label>
        <p className="muted">
          Save changes first, then verify the saved live connection before turning demo mode off for customers.
        </p>
        <div className="wizard-delivery-actions">
          <button className="button button-primary" disabled={saving}>
            {saving ? "Saving..." : "Save optional connection"}
          </button>
          <button
            className="button button-secondary"
            type="button"
            onClick={verifyConnection}
            disabled={checkingConnection || saving}
          >
            {checkingConnection ? "Checking..." : "Verify saved live AI connection"}
          </button>
        </div>
      </form>
    </section>
  );
}
