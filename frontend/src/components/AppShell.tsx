"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";

import { api, ApiError, logout, type Me } from "@/lib/api";
import { setLang, useT } from "@/lib/i18n";

const MeContext = createContext<Me | null>(null);

/** The logged-in user. Only use inside pages wrapped by AppShell. */
export function useMe(): Me {
  const me = useContext(MeContext);
  if (!me) throw new Error("useMe() used outside AppShell");
  return me;
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { t, lang } = useT();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Me>("/me").then(setMe, (e: unknown) => {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(e instanceof Error ? e.message : String(e));
    });
  }, [router]);

  const nav = [
    { href: "/", label: t("home") },
    { href: "/ask", label: t("ask") },
    { href: "/upload", label: t("upload") },
    { href: "/documents", label: t("documents") },
  ];

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="bg-brand text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link href="/" className="text-lg font-semibold">
            {t("appName")}
          </Link>
          <nav className="flex gap-1">
            {nav.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={`rounded px-3 py-1.5 text-sm ${
                  pathname === n.href ? "bg-white/20" : "hover:bg-white/10"
                }`}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <button
              onClick={() => setLang(lang === "en" ? "hi" : "en")}
              className="rounded border border-white/40 px-2 py-1 hover:bg-white/10"
            >
              {lang === "en" ? "हिंदी" : "English"}
            </button>
            {me && (
              <span className="opacity-90">
                {me.name} · {me.org_unit.code}
              </span>
            )}
            <button
              onClick={() => {
                logout();
                router.replace("/login");
              }}
              className="rounded bg-white px-3 py-1 font-medium text-brand hover:bg-brand-soft"
            >
              {t("logout")}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
        {!me && !error && <p className="text-gray-500">{t("loading")}</p>}
        {me && <MeContext.Provider value={me}>{children}</MeContext.Provider>}
      </main>
    </div>
  );
}
