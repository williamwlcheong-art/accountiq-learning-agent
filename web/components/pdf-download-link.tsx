"use client";

import { MouseEvent, useState } from "react";

type PdfDownloadLinkProps = {
  reportId: number;
  companyName?: string;
  className?: string;
};

const FALLBACK_MESSAGE =
  "We could not build the PDF right now. You can still open the report online. Reply to your confirmation email and we will send the PDF to you.";

function safeFilename(companyName: string | undefined, reportId: number) {
  const base = (companyName || `report-${reportId}`).replace(/[^a-z0-9]+/gi, "-").replace(/^-+|-+$/g, "").toLowerCase();
  return `${base || `report-${reportId}`}-valuation.pdf`;
}

export function PdfDownloadLink({ reportId, companyName, className = "button button-secondary" }: PdfDownloadLinkProps) {
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState("");
  const href = `/api/backend/wizard/report/${reportId}/pdf`;

  async function download(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    if (state === "loading") return;
    setState("loading");
    setMessage("");
    try {
      const response = await fetch(href, { credentials: "include" });
      if (!response.ok) {
        let detail = FALLBACK_MESSAGE;
        try {
          const body = (await response.json()) as { detail?: unknown };
          if (typeof body.detail === "string" && body.detail.trim()) detail = body.detail;
        } catch {
          // Non-JSON error body: keep the fallback message.
        }
        setState("error");
        setMessage(detail);
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = safeFilename(companyName, reportId);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setState("idle");
    } catch {
      setState("error");
      setMessage(FALLBACK_MESSAGE);
    }
  }

  return (
    <span className="pdf-download">
      <a className={className} href={href} onClick={download} aria-busy={state === "loading"}>
        {state === "loading" ? "Preparing PDF..." : "Download PDF"}
      </a>
      {state === "error" ? (
        <span role="alert" className="pdf-download-error">
          {message}
        </span>
      ) : null}
    </span>
  );
}
