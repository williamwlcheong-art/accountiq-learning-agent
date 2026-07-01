import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AccountIQ",
  description: "Fixed-fee SME valuation reports with adviser review.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
