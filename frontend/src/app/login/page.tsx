"use client";

import { Eye, EyeOff, Languages, LogIn, ShieldCheck, WifiOff } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LogoMark } from "@/components/AppShell";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { login } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { type LabelKey, setLang, useT } from "@/lib/i18n";
import { safeInternalPath } from "@/lib/sources";

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary for Next's static render pass.
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

const TRUST: { icon: typeof ShieldCheck; title: LabelKey; body: LabelKey }[] = [
  { icon: ShieldCheck, title: "login.trustSourced", body: "login.trustSourcedBody" },
  { icon: Languages, title: "login.trustBilingual", body: "login.trustBilingualBody" },
  { icon: WifiOff, title: "login.trustOffline", body: "login.trustOfflineBody" },
];

function BrandPanel() {
  const { t } = useT();
  return (
    <aside className="flex flex-col justify-between gap-8 bg-sidebar px-6 py-8 text-white sm:px-10 lg:w-[44%] lg:max-w-xl lg:py-12">
      <div className="flex items-center gap-3">
        <LogoMark className="size-11" />
        <span className="leading-tight">
          <span className="block text-lg font-bold tracking-tight">{t("appName")}</span>
          <span className="block text-xs text-sidebar-text">CMPDI · CIL</span>
        </span>
      </div>
      <div className="space-y-6">
        <p className="max-w-md text-xl leading-snug font-semibold sm:text-2xl">{t("tagline")}</p>
        <ul className="space-y-4">
          {TRUST.map(({ icon: Icon, title, body }) => (
            <li key={title} className="flex items-start gap-3">
              <span
                aria-hidden
                className="grid size-9 shrink-0 place-items-center rounded-full bg-sidebar-active text-accent"
              >
                <Icon size={18} />
              </span>
              <span>
                <span className="block text-sm font-semibold">{t(title)}</span>
                <span className="block text-xs text-sidebar-text">{t(body)}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
      <p className="hidden text-xs text-sidebar-text lg:block">{t("shell.official")}</p>
    </aside>
  );
}

function LoginForm() {
  const router = useRouter();
  // Where the person was when their session expired, so they land back there.
  // Only an in-app path counts: anything else could bounce them off-site, and it
  // must not make the page claim a session ended either.
  const requested = useSearchParams().get("next");
  const next = safeInternalPath(requested);
  const { t, lang } = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = `${t("signIn")} · KoylaSetu AI`;
  }, [t]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace(next ?? "/");
    } catch (err) {
      setError(errorText(err, t));
      setBusy(false);
    }
  }

  const otherLang = lang === "en" ? "hi" : "en";

  return (
    <div className="flex flex-1 flex-col bg-background lg:flex-row">
      <BrandPanel />
      <main className="flex flex-1 flex-col items-center justify-center gap-4 px-4 py-8 sm:px-8">
        <div className="flex w-full max-w-md justify-end">
          <button
            type="button"
            onClick={() => setLang(otherLang)}
            title={t("shell.switchLanguage")}
            className="inline-flex h-9 items-center gap-2 rounded-full border border-line-strong bg-surface px-3 text-xs font-semibold text-brand hover:bg-brand-tint"
          >
            <Languages size={16} aria-hidden />
            <span lang={otherLang}>{otherLang === "hi" ? "हिंदी" : "English"}</span>
          </button>
        </div>
        <Card className="w-full max-w-md">
          <h1 className="text-xl leading-8 font-semibold tracking-tight text-strong">{t("login.formTitle")}</h1>
          <p className="mt-1 text-sm text-muted">{t("login.formSubtitle")}</p>
          {next && (
            <Alert tone="warning" className="mt-4">
              {t("login.sessionExpired")}
            </Alert>
          )}
          <form onSubmit={onSubmit} className="mt-5 space-y-4">
            <Field label={t("email")} required>
              <Input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field label={t("password")} required>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pr-11"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={t("login.showPassword")}
                  aria-pressed={showPassword}
                  title={t("login.showPassword")}
                  className="absolute top-1/2 right-1.5 grid size-8 -translate-y-1/2 place-items-center rounded-full text-muted hover:bg-brand-soft hover:text-brand"
                >
                  {showPassword ? <EyeOff size={16} aria-hidden /> : <Eye size={16} aria-hidden />}
                </button>
              </div>
            </Field>
            {error && <Alert tone="danger">{error}</Alert>}
            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={busy}
              icon={<LogIn size={16} aria-hidden />}
              className="w-full"
            >
              {busy ? t("signingIn") : t("signIn")}
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
