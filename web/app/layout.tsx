import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AccountIQ",
  description: "Financial intelligence report generation for SMEs",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
