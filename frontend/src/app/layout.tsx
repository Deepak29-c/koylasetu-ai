import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";

import HtmlLang from "@/components/HtmlLang";
import { ToastProvider } from "@/components/ui/Toast";

import "./globals.css";

// Self-hosted variable fonts: the build and the app must work with no internet access.
const montserrat = localFont({
  src: "../fonts/montserrat-latin-wght-normal.woff2",
  weight: "100 900",
  variable: "--font-montserrat",
  display: "swap",
});

const devanagari = localFont({
  src: "../fonts/noto-sans-devanagari-devanagari-wght-normal.woff2",
  weight: "100 900",
  variable: "--font-devanagari",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "KoylaSetu AI", template: "%s · KoylaSetu AI" },
  description: "Verified AI Reporting & Parliamentary-Reply Assistant for CMPDI / CIL",
};

export const viewport: Viewport = {
  themeColor: "#0b2e59",
};

// Runs before hydration so <html lang> (and screen readers) match the saved language
// from the first paint. <HtmlLang /> keeps it in step after that.
const setLangEarly = `try{if(localStorage.getItem("ks_lang")==="hi")document.documentElement.lang="hi"}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${montserrat.variable} ${devanagari.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: setLangEarly }} />
      </head>
      <body className="flex min-h-full flex-col">
        <HtmlLang />
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
