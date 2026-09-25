"use client";

import { useState } from "react";

import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import Drawer from "@/components/ui/Drawer";
import { Checkbox, Field, Fieldset, Input, Select } from "@/components/ui/Field";
import RecordList from "@/components/ui/RecordList";
import { ALL_ROLES, createUser, type OrgUnitOut, type Role, updateUser, type UserRow } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { type LabelKey, useT } from "@/lib/i18n";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD = 8;

type Errors = Partial<Record<"name" | "email" | "password" | "roles" | "unit", string>>;

/**
 * Creates a user, or (given `user`) changes an existing user's roles and unit. Name and
 * email are fixed after creation, so the edit form shows them read-only.
 */
export default function UserFormDrawer({
  user,
  orgUnits,
  onClose,
  onSaved,
}: {
  user?: UserRow;
  orgUnits: OrgUnitOut[];
  onClose: () => void;
  onSaved: (saved: UserRow) => void;
}) {
  const { t } = useT();
  const editing = !!user;
  const formId = editing ? "user-edit-form" : "user-create-form";

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roles, setRoles] = useState<Set<Role>>(() => new Set((user?.roles ?? []) as Role[]));
  const [unit, setUnit] = useState(user?.org_unit.id ?? "");
  const [errors, setErrors] = useState<Errors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function validate(): Errors {
    const e: Errors = {};
    if (!editing) {
      if (!name.trim()) e.name = t("users.nameRequired");
      if (!EMAIL_RE.test(email.trim())) e.email = t("users.emailInvalid");
      if (password.length < MIN_PASSWORD) e.password = t("users.passwordTooShort");
    }
    if (roles.size === 0) e.roles = t("atLeastOneRole");
    if (!unit) e.unit = t("users.unitRequired");
    return e;
  }

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length > 0) return;
    setSaving(true);
    setServerError(null);
    try {
      const saved = user
        ? await updateUser(user.id, { roles: [...roles], org_unit_id: unit })
        : await createUser({
            name: name.trim(),
            email: email.trim(),
            password,
            roles: [...roles],
            org_unit_id: unit,
          });
      onSaved(saved);
    } catch (err) {
      setServerError(errorText(err, t));
      setSaving(false);
    }
  }

  function toggleRole(r: Role, on: boolean) {
    const next = new Set(roles);
    if (on) next.add(r);
    else next.delete(r);
    setRoles(next);
    if (errors.roles && next.size > 0) setErrors({ ...errors, roles: undefined });
  }

  return (
    <Drawer
      title={editing ? t("users.editTitle") : t("createUserTitle")}
      eyebrow={t("users")}
      description={editing ? t("users.editDescription") : t("users.createDescription")}
      onClose={saving ? () => {} : onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            {t("cancel")}
          </Button>
          <Button type="submit" form={formId} variant="primary" loading={saving}>
            {editing ? (saving ? t("saving") : t("users.saveChanges")) : saving ? t("creating") : t("createButton")}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} noValidate className="space-y-5">
        {serverError && <Alert tone="danger">{serverError}</Alert>}

        {user ? (
          <RecordList
            columns={2}
            items={[
              { label: t("name"), value: user.name },
              { label: t("email"), value: user.email },
            ]}
          />
        ) : (
          <>
            <Field label={t("name")} required error={errors.name}>
              <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
            </Field>
            <Field label={t("email")} required error={errors.email}>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="off"
                inputMode="email"
              />
            </Field>
            <Field label={t("password")} required hint={t("users.passwordHint")} error={errors.password}>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                minLength={MIN_PASSWORD}
              />
            </Field>
          </>
        )}

        <Field label={t("orgUnit")} required error={errors.unit}>
          <Select value={unit} onChange={(e) => setUnit(e.target.value)}>
            <option value="" disabled>
              {t("users.unitPlaceholder")}
            </option>
            {orgUnits.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name} ({o.code})
              </option>
            ))}
          </Select>
        </Field>

        <Fieldset legend={t("roles")} hint={t("users.rolesHint")} error={errors.roles}>
          <div className="space-y-3 rounded-panel border border-line bg-surface-subtle p-4">
            {ALL_ROLES.map((r) => (
              <Checkbox
                key={r}
                checked={roles.has(r)}
                onChange={(e) => toggleRole(r, e.target.checked)}
                label={<span className="font-medium text-strong">{t(`role.${r}` as LabelKey)}</span>}
                description={t(`users.roleDesc.${r}` as LabelKey)}
              />
            ))}
          </div>
        </Fieldset>
      </form>
    </Drawer>
  );
}
