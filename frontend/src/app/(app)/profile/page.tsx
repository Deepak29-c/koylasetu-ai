"use client";

import { KeyRound, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useMe } from "@/components/AppShell";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import RecordList, { MonoId } from "@/components/ui/RecordList";
import { useToast } from "@/components/ui/Toast";
import { ApiError, changePassword, logout } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

export default function ProfilePage() {
  const me = useMe();
  const router = useRouter();
  const toast = useToast();
  const { t } = useT();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [nextError, setNextError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNextError(null);
    setConfirmError(null);
    if (next.length < 8) {
      setNextError(t("newPasswordTooShort"));
      return;
    }
    if (next !== confirm) {
      setConfirmError(t("passwordsDontMatch"));
      return;
    }
    setBusy(true);
    try {
      await changePassword(current, next);
      toast({ tone: "success", title: t("passwordChanged") });
      logout();
      router.replace("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("profile")} description={t("profile.description")} />
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader icon={<UserRound />} title={t("profile.account")} />
          <RecordList
            items={[
              { label: t("name"), value: me.name },
              { label: t("email"), value: me.email },
              {
                label: t("roles"),
                value:
                  me.roles.length > 0 ? (
                    <span className="flex flex-wrap gap-1.5">
                      {me.roles.map((r) => (
                        <Badge key={r} tone="brand">
                          {t(`role.${r}` as LabelKey)}
                        </Badge>
                      ))}
                    </span>
                  ) : null,
              },
              {
                label: t("orgUnit"),
                value: (
                  <span className="flex flex-wrap items-center gap-2">
                    {me.org_unit.name}
                    <MonoId>{me.org_unit.code}</MonoId>
                  </span>
                ),
              },
            ]}
          />
        </Card>

        <Card>
          <CardHeader icon={<KeyRound />} title={t("changePassword")} subtitle={t("changePasswordHelp")} />
          <form onSubmit={onSubmit} className="space-y-4">
            <Field label={t("currentPassword")} required>
              <Input
                type="password"
                autoComplete="current-password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </Field>
            <Field label={t("newPassword")} required hint={t("profile.newPasswordHint")} error={nextError}>
              <Input
                type="password"
                minLength={8}
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
            </Field>
            <Field label={t("confirmNewPassword")} required hint={t("profile.confirmHint")} error={confirmError}>
              <Input
                type="password"
                minLength={8}
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </Field>
            {error && <Alert tone="danger">{error}</Alert>}
            <div className="flex justify-end">
              <Button type="submit" variant="primary" loading={busy}>
                {busy ? t("changingPassword") : t("changePasswordButton")}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
