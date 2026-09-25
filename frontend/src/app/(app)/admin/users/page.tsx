"use client";

import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import ConfirmDialog from "@/components/ConfirmDialog";
import {
  ALL_ROLES,
  ApiError,
  createUser,
  listOrgUnits,
  listUsers,
  type OrgUnitOut,
  type Role,
  updateUser,
  type UserRow,
} from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

function RoleCheckboxes({
  selected,
  onChange,
}: {
  selected: Set<Role>;
  onChange: (next: Set<Role>) => void;
}) {
  const { t } = useT();
  return (
    <div className="flex flex-wrap gap-3">
      {ALL_ROLES.map((r) => (
        <label key={r} className="flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            checked={selected.has(r)}
            onChange={(e) => {
              const next = new Set(selected);
              if (e.target.checked) next.add(r);
              else next.delete(r);
              onChange(next);
            }}
          />
          {t(`role.${r}` as LabelKey)}
        </label>
      ))}
    </div>
  );
}

export default function AdminUsersPage() {
  const me = useMe();
  const { t } = useT();
  const allowed = me.permissions.includes("manage_admin");

  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [orgUnits, setOrgUnits] = useState<OrgUnitOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      Promise.all([listUsers(), listOrgUnits()]).then(
        ([u, o]) => {
          setUsers(u);
          setOrgUnits(o);
          setError(null);
        },
        (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
      ),
    [],
  );

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  // --- Create form ---
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRoles, setNewRoles] = useState<Set<Role>>(new Set());
  const [newUnit, setNewUnit] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function submitCreate(e: React.FormEvent) {
    e.preventDefault();
    if (newRoles.size === 0) {
      setCreateError(t("atLeastOneRole"));
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      await createUser({
        name: newName,
        email: newEmail,
        password: newPassword,
        roles: [...newRoles],
        org_unit_id: newUnit,
      });
      setNewName("");
      setNewEmail("");
      setNewPassword("");
      setNewRoles(new Set());
      setShowCreate(false);
      await load();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  // --- Inline edit ---
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editRoles, setEditRoles] = useState<Set<Role>>(new Set());
  const [editUnit, setEditUnit] = useState("");
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  function startEdit(u: UserRow) {
    setEditingId(u.id);
    setEditRoles(new Set(u.roles as Role[]));
    setEditUnit(u.org_unit.id);
    setEditError(null);
  }

  async function saveEdit(id: string) {
    if (editRoles.size === 0) {
      setEditError(t("atLeastOneRole"));
      return;
    }
    setSaving(true);
    setEditError(null);
    try {
      await updateUser(id, { roles: [...editRoles], org_unit_id: editUnit });
      setEditingId(null);
      await load();
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  // Deactivating locks someone out, so it is confirmed first. Reactivating is harmless
  // and stays a single click.
  const [confirmDeactivate, setConfirmDeactivate] = useState<UserRow | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  async function toggleActive(u: UserRow) {
    setError(null);
    setConfirmDeactivate(null);
    setTogglingId(u.id);
    try {
      await updateUser(u.id, { is_active: !u.is_active });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setTogglingId(null);
    }
  }

  if (!allowed) return <p className="text-gray-600">{t("noPermission")}</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("users")}</h1>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="rounded bg-brand px-4 py-2 text-sm font-medium text-white"
        >
          {showCreate ? t("cancel") : t("newUser")}
        </button>
      </div>

      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}

      {showCreate && (
        <form onSubmit={submitCreate} className="space-y-4 rounded border bg-white p-4">
          <h2 className="font-medium">{t("createUserTitle")}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="text-sm font-medium">{t("name")}</span>
              <input
                required
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="mt-1 w-full rounded border px-3 py-2"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium">{t("email")}</span>
              <input
                type="email"
                required
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="mt-1 w-full rounded border px-3 py-2"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium">{t("password")}</span>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="mt-1 w-full rounded border px-3 py-2"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium">{t("orgUnit")}</span>
              <select
                required
                value={newUnit}
                onChange={(e) => setNewUnit(e.target.value)}
                className="mt-1 w-full rounded border px-3 py-2"
              >
                <option value="" disabled>
                  —
                </option>
                {orgUnits?.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} ({o.code})
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div>
            <span className="text-sm font-medium">{t("roles")}</span>
            <div className="mt-1">
              <RoleCheckboxes selected={newRoles} onChange={setNewRoles} />
            </div>
          </div>
          {createError && <p className="text-sm text-red-700">{createError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="rounded bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {creating ? t("creating") : t("createButton")}
          </button>
        </form>
      )}

      {users === null && !error && <p className="text-gray-500">{t("loading")}</p>}
      {users?.length === 0 && <p className="text-gray-600">{t("noUsers")}</p>}
      {users && users.length > 0 && (
        <div className="overflow-x-auto rounded border bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-2 font-medium">{t("name")}</th>
                <th className="px-4 py-2 font-medium">{t("email")}</th>
                <th className="px-4 py-2 font-medium">{t("roles")}</th>
                <th className="px-4 py-2 font-medium">{t("orgUnit")}</th>
                <th className="px-4 py-2 font-medium">{t("status")}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const editing = editingId === u.id;
                return (
                  <tr key={u.id} className="border-t align-top">
                    <td className="px-4 py-2 font-medium">{u.name}</td>
                    <td className="px-4 py-2 text-gray-600">{u.email}</td>
                    <td className="px-4 py-2">
                      {editing ? (
                        <RoleCheckboxes selected={editRoles} onChange={setEditRoles} />
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {u.roles.map((r) => (
                            <span key={r} className="rounded bg-gray-100 px-2 py-0.5 text-xs">
                              {t(`role.${r}` as LabelKey)}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      {editing ? (
                        <select
                          value={editUnit}
                          onChange={(e) => setEditUnit(e.target.value)}
                          className="rounded border px-2 py-1"
                        >
                          {orgUnits?.map((o) => (
                            <option key={o.id} value={o.id}>
                              {o.code}
                            </option>
                          ))}
                        </select>
                      ) : (
                        u.org_unit.code
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-medium ${
                          u.is_active ? "bg-green-100 text-green-800" : "bg-gray-200 text-gray-700"
                        }`}
                      >
                        {u.is_active ? t("active") : t("inactive")}
                      </span>
                    </td>
                    <td className="px-4 py-2 whitespace-nowrap">
                      {editing ? (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => saveEdit(u.id)}
                            disabled={saving}
                            className="rounded bg-brand px-2 py-1 text-xs font-medium text-white disabled:opacity-60"
                          >
                            {saving ? t("saving") : t("save")}
                          </button>
                          <button
                            onClick={() => setEditingId(null)}
                            className="text-xs text-gray-600 underline"
                          >
                            {t("cancel")}
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-3">
                          <button onClick={() => startEdit(u)} className="text-xs text-brand underline">
                            {t("edit")}
                          </button>
                          <button
                            onClick={() =>
                              u.is_active ? setConfirmDeactivate(u) : toggleActive(u)
                            }
                            disabled={(u.id === me.id && u.is_active) || togglingId === u.id}
                            title={u.id === me.id && u.is_active ? t("cannotDeactivateSelf") : undefined}
                            className="text-xs text-brand underline disabled:cursor-not-allowed disabled:text-gray-400 disabled:no-underline"
                          >
                            {u.is_active ? t("deactivate") : t("reactivate")}
                          </button>
                        </div>
                      )}
                      {editing && editError && <p className="mt-1 text-xs text-red-700">{editError}</p>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {confirmDeactivate && (
        <ConfirmDialog
          title={t("users.deactivateConfirm")}
          body={`${confirmDeactivate.name} (${confirmDeactivate.email}) — ${t("users.deactivateConfirmBody")}`}
          confirmLabel={t("deactivate")}
          danger
          busy={togglingId === confirmDeactivate.id}
          onConfirm={() => toggleActive(confirmDeactivate)}
          onCancel={() => setConfirmDeactivate(null)}
        />
      )}
    </div>
  );
}
