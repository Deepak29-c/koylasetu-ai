"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useMe } from "@/components/AppShell";
import { ApiError, changePassword, logout } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function ProfilePage() {
  const me = useMe();
  const router = useRouter();
  const { t } = useT();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (next.length < 8) {
      setError(t("newPasswordTooShort"));
      return;
    }
    if (next !== confirm) {
      setError(t("passwordsDontMatch"));
      return;
    }
    setBusy(true);
    try {
      await changePassword(current, next);
      logout();
      router.replace("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div className="max-w-sm space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("profile")}</h1>
        <p className="text-gray-600">
          {me.name} · {me.email}
        </p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-6 shadow-sm">
        <h2 className="font-medium">{t("changePassword")}</h2>
        <p className="text-sm text-gray-500">{t("changePasswordHelp")}</p>
        <label className="block">
          <span className="text-sm font-medium">{t("currentPassword")}</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">{t("newPassword")}</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">{t("confirmNewPassword")}</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-brand py-2.5 font-medium text-white disabled:opacity-60"
        >
          {busy ? t("changingPassword") : t("changePasswordButton")}
        </button>
      </form>
    </div>
  );
}
