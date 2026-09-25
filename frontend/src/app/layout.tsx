import type { Metadata } from "next";

import HtmlLang from "@/components/HtmlLang";

import "./globals.css";

export const metadata: Metadata = {
  title: "KoylaSetu AI",
  description: "Verified AI Reporting & Parliamentary-Reply Assistant for CMPDI / CIL",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  // lang starts as "en" and is corrected on the client by <HtmlLang /> — this is a
  // server component, so it can only ever render one value.
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <HtmlLang />
        {children}
      </body>
    </html>
  );
}
