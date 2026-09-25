"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { login } from "@/lib/api";
import { setLang, useT } from "@/lib/i18n";

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary for Next's static render pass.
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  // Where the person was when their session expired, so they land back there.
  const next = useSearchParams().get("next");
  const { t, lang } = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      // Only ever an in-app path, never an absolute URL an attacker could supply.
      router.replace(next?.startsWith("/") && !next.startsWith("//") ? next : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-semibold text-brand">{t("appName")}</h1>
          <p className="mt-1 text-sm text-gray-600">{t("tagline")}</p>
        </div>
        {next && (
          <p className="mb-4 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            {t("login.sessionExpired")}
          </p>
        )}
        <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-6 shadow-sm">
          <label className="block">
            <span className="text-sm font-medium">{t("email")}</span>
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t("password")}</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
          {error && <p className="text-sm text-red-700">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded bg-brand py-2.5 font-medium text-white disabled:opacity-60"
          >
            {busy ? t("signingIn") : t("signIn")}
          </button>
        </form>
        <button
          onClick={() => setLang(lang === "en" ? "hi" : "en")}
          className="mx-auto mt-4 block text-sm text-brand underline"
        >
          {lang === "en" ? "हिंदी" : "English"}
        </button>
      </div>
    </div>
  );
}
