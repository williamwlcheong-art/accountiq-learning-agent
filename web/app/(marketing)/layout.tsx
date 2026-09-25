import { Instrument_Sans, Newsreader } from "next/font/google";
import type { ReactNode } from "react";

import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";

import "@/components/marketing/marketing.css";

// Loaded here rather than in the root layout, so the signed-in app does not download them.
const display = Newsreader({
  subsets: ["latin"],
  style: ["normal", "italic"],
  axes: ["opsz"],
  variable: "--font-display",
  display: "swap",
});
const sans = Instrument_Sans({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className={`marketing-page ${display.variable} ${sans.variable}`}>
      <a className="marketing-skip-link" href="#main-content">
        Skip to main content
      </a>
      <SiteHeader />
      <main id="main-content">{children}</main>
      <SiteFooter />
    </div>
  );
}
