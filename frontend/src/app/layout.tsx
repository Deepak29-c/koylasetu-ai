import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KoylaSetu AI",
  description: "Verified AI Reporting & Parliamentary-Reply Assistant for CMPDI / CIL",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
