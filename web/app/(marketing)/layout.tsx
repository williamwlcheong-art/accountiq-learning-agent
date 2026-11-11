import { Instrument_Sans } from "next/font/google";
import type { ReactNode } from "react";

import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";

import "@/components/marketing/marketing.css";

// Loaded here rather than in the root layout, so the signed-in app does not download it.
const sans = Instrument_Sans({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className={`marketing-page ${sans.variable}`}>
      <a className="marketing-skip-link" href="#main-content">
        Skip to main content
      </a>
      <SiteHeader />
      <main id="main-content">{children}</main>
      <SiteFooter />
    </div>
  );
}
