"use client";

import { Pencil, UserPlus, Users as UsersIcon, UserSearch } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import UserFormDrawer from "@/components/admin/UserFormDrawer";
import { useMe } from "@/components/AppShell";
import ConfirmDialog from "@/components/ConfirmDialog";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Field, Select } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import { TableSkeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  Pagination,
  SearchInput,
  TD,
  TH,
  THead,
  TR,
  Table,
  TableFrame,
  TableToolbar,
  usePaged,
  useSort,
} from "@/components/ui/Table";
import Tabs from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { ALL_ROLES, listOrgUnits, listUsers, type OrgUnitOut, type Role, updateUser, type UserRow } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { type LabelKey, useT } from "@/lib/i18n";

const PAGE_SIZE = 25;

type StatusFilter = "all" | "active" | "inactive";
type SortKey = "name" | "unit" | "status";

export default function AdminUsersPage() {
  const me = useMe();
  const { t } = useT();
  const toast = useToast();
  const allowed = me.permissions.includes("manage_admin");

  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [orgUnits, setOrgUnits] = useState<OrgUnitOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  // A reload after a change keeps the current list on screen until the new one arrives.
  const load = useCallback(
    () =>
      Promise.all([listUsers(), listOrgUnits()]).then(
        ([u, o]) => {
          setUsers(u);
          setOrgUnits(o);
          setError(null);
        },
        (e: unknown) => setError(errorText(e)),
      ),
    [],
  );

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  // --- Filters ---
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<Role | "">("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const matchesSearchAndRole = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (users ?? []).filter(
      (u) =>
        (!q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)) &&
        (!roleFilter || u.roles.includes(roleFilter)),
    );
  }, [users, query, roleFilter]);

  const filtered = useMemo(
    () =>
      matchesSearchAndRole.filter(
        (u) => statusFilter === "all" || (statusFilter === "active" ? u.is_active : !u.is_active),
      ),
    [matchesSearchAndRole, statusFilter],
  );

  const counts = useMemo(
    () => ({
      all: matchesSearchAndRole.length,
      active: matchesSearchAndRole.filter((u) => u.is_active).length,
      inactive: matchesSearchAndRole.filter((u) => !u.is_active).length,
    }),
    [matchesSearchAndRole],
  );

  const { sorted, header } = useSort<UserRow, SortKey>(
    filtered,
    (u, key) => (key === "name" ? u.name.toLowerCase() : key === "unit" ? u.org_unit.code : u.is_active ? 0 : 1),
    { key: "name", dir: "asc" },
  );
  const paged = usePaged(sorted, PAGE_SIZE);

  function onQuery(v: string) {
    setQuery(v);
    paged.setPage(1);
  }
  function onRole(v: Role | "") {
    setRoleFilter(v);
    paged.setPage(1);
  }
  function onStatus(v: StatusFilter) {
    setStatusFilter(v);
    paged.setPage(1);
  }
  function clearFilters() {
    setQuery("");
    setRoleFilter("");
    setStatusFilter("all");
    paged.setPage(1);
  }
  const hasFilters = query.trim() !== "" || roleFilter !== "" || statusFilter !== "all";

  // --- Create / edit drawer ---
  const [drawer, setDrawer] = useState<{ user?: UserRow } | null>(null);

  function onSaved(saved: UserRow) {
    const wasEdit = !!drawer?.user;
    setDrawer(null);
    toast({ title: wasEdit ? t("users.updatedToast") : t("users.createdToast"), body: `${saved.name} (${saved.email})` });
    load();
  }

  // --- Activate / deactivate ---
  // Both directions are confirmed: deactivating locks someone out, reactivating gives
  // access back.
  const [confirming, setConfirming] = useState<UserRow | null>(null);
  const [toggling, setToggling] = useState(false);

  async function toggleActive(u: UserRow) {
    setToggling(true);
    try {
      await updateUser(u.id, { is_active: !u.is_active });
      toast({
        title: u.is_active ? t("users.deactivatedToast") : t("users.reactivatedToast"),
        body: `${u.name} (${u.email})`,
      });
      setConfirming(null);
      await load();
    } catch (err) {
      setConfirming(null);
      toast({ tone: "danger", title: t("ui.somethingWrong"), body: errorText(err, t) });
    } finally {
      setToggling(false);
    }
  }

  if (!allowed) {
    return (
      <>
        <PageHeader title={t("users")} />
        <Alert tone="warning">{t("noPermission")}</Alert>
      </>
    );
  }

  function rowActions(u: UserRow) {
    const self = u.id === me.id;
    return (
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          icon={<Pencil size={14} aria-hidden />}
          onClick={() => setDrawer({ user: u })}
          aria-label={`${t("users.editUser")}: ${u.name}`}
        >
          {t("users.editUser")}
        </Button>
        {u.is_active ? (
          <Button
            variant="danger-outline"
            size="sm"
            onClick={() => setConfirming(u)}
            disabled={self}
            title={self ? t("cannotDeactivateSelf") : undefined}
            aria-label={`${t("deactivate")}: ${u.name}`}
          >
            {t("deactivate")}
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirming(u)}
            aria-label={`${t("reactivate")}: ${u.name}`}
          >
            {t("reactivate")}
          </Button>
        )}
      </div>
    );
  }

  function roleBadges(u: UserRow) {
    return (
      <div className="flex flex-wrap gap-1">
        {u.roles.map((r) => (
          <Badge key={r} tone="brand">
            {t(`role.${r}` as LabelKey)}
          </Badge>
        ))}
      </div>
    );
  }

  function nameCell(u: UserRow) {
    return (
      <div className="min-w-0">
        <span className="flex flex-wrap items-center gap-2 font-medium text-strong">
          {u.name}
          {u.id === me.id && <Badge tone="info">{t("users.you")}</Badge>}
        </span>
        <span className="block truncate text-xs text-subtle">{u.email}</span>
      </div>
    );
  }

  const statusTabs = (
    <Tabs<StatusFilter>
      label={t("users.statusFilter")}
      value={statusFilter}
      onChange={onStatus}
      items={[
        { value: "all", label: t("users.statusAll"), count: counts.all },
        { value: "active", label: t("active"), count: counts.active },
        { value: "inactive", label: t("inactive"), count: counts.inactive },
      ]}
    />
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("users")}
        description={t("users.description")}
        actions={
          <Button
            variant="primary"
            icon={<UserPlus size={16} aria-hidden />}
            onClick={() => setDrawer({})}
            disabled={users === null}
          >
            {t("newUser")}
          </Button>
        }
      />

      {error && (
        <Alert
          tone="danger"
          action={
            <Button variant="outline" size="sm" onClick={() => load()}>
              {t("retry")}
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {users === null ? (
        error ? null : (
          <TableFrame>
            <TableSkeleton rows={6} columns={5} />
          </TableFrame>
        )
      ) : users.length === 0 ? (
        <EmptyState
          icon={<UsersIcon />}
          title={t("noUsers")}
          action={
            <Button variant="primary" icon={<UserPlus size={16} aria-hidden />} onClick={() => setDrawer({})}>
              {t("newUser")}
            </Button>
          }
        >
          {t("users.noUsersBody")}
        </EmptyState>
      ) : (
        <TableFrame>
          <TableToolbar
            title={t("users.listTitle")}
            count={filtered.length}
            total={users.length}
            filters={
              <div className="flex w-full flex-wrap items-center gap-3 sm:w-auto">
                {statusTabs}
                <Field label={t("users.roleFilter")} hideLabel className="w-full sm:w-44">
                  <Select
                    value={roleFilter}
                    onChange={(e) => onRole(e.target.value as Role | "")}
                    className="h-9 rounded-full"
                  >
                    <option value="">{t("users.allRoles")}</option>
                    {ALL_ROLES.map((r) => (
                      <option key={r} value={r}>
                        {t(`role.${r}` as LabelKey)}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            }
            search={<SearchInput value={query} onChange={onQuery} placeholder={t("users.searchPlaceholder")} />}
          />

          {filtered.length === 0 ? (
            <div className="px-5 pb-5">
              <EmptyState
                compact
                icon={<UserSearch />}
                title={t("users.noMatches")}
                action={
                  hasFilters ? (
                    <Button variant="outline" size="sm" onClick={clearFilters}>
                      {t("ui.clearFilters")}
                    </Button>
                  ) : undefined
                }
              >
                {t("users.noMatchesBody")}
              </EmptyState>
            </div>
          ) : (
            <>
              <div className="hidden sm:block">
                <Table caption={t("users.listTitle")}>
                  <THead>
                    <TH sort={header("name")}>{t("name")}</TH>
                    <TH>{t("roles")}</TH>
                    <TH sort={header("unit")}>{t("orgUnit")}</TH>
                    <TH sort={header("status")}>{t("status")}</TH>
                    <TH align="right">{t("users.actions")}</TH>
                  </THead>
                  <tbody>
                    {paged.rows.map((u) => (
                      <TR key={u.id}>
                        <TD className="max-w-72">{nameCell(u)}</TD>
                        <TD>{roleBadges(u)}</TD>
                        <TD>
                          <span title={u.org_unit.name} className="whitespace-nowrap">
                            {u.org_unit.code}
                          </span>
                        </TD>
                        <TD>
                          <StatusBadge kind="user" value={u.is_active ? "active" : "inactive"} />
                        </TD>
                        <TD align="right">{rowActions(u)}</TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </div>

              <ul className="divide-y divide-line border-t border-line sm:hidden">
                {paged.rows.map((u) => (
                  <li key={u.id} className="space-y-3 px-5 py-4">
                    <div className="flex items-start justify-between gap-3">
                      {nameCell(u)}
                      <StatusBadge kind="user" value={u.is_active ? "active" : "inactive"} />
                    </div>
                    {roleBadges(u)}
                    <p className="text-xs text-muted">
                      {t("orgUnit")}: <span className="text-foreground">{u.org_unit.name} ({u.org_unit.code})</span>
                    </p>
                    <div className="flex justify-start">{rowActions(u)}</div>
                  </li>
                ))}
              </ul>

              <Pagination
                page={paged.page}
                pageCount={paged.pageCount}
                onPage={paged.setPage}
                from={paged.from}
                to={paged.to}
                total={paged.total}
              />
            </>
          )}
        </TableFrame>
      )}

      {drawer && (
        <UserFormDrawer
          key={drawer.user?.id ?? "new"}
          user={drawer.user}
          orgUnits={orgUnits}
          onClose={() => setDrawer(null)}
          onSaved={onSaved}
        />
      )}

      {confirming &&
        (confirming.is_active ? (
          <ConfirmDialog
            title={t("users.deactivateConfirm")}
            body={`${confirming.name} (${confirming.email}) — ${t("users.deactivateConfirmBody")}`}
            confirmLabel={t("deactivate")}
            danger
            busy={toggling}
            onConfirm={() => toggleActive(confirming)}
            onCancel={() => setConfirming(null)}
          />
        ) : (
          <ConfirmDialog
            title={t("users.reactivateConfirm")}
            body={`${confirming.name} (${confirming.email}) — ${t("users.reactivateConfirmBody")}`}
            confirmLabel={t("reactivate")}
            positive
            busy={toggling}
            onConfirm={() => toggleActive(confirming)}
            onCancel={() => setConfirming(null)}
          />
        ))}
    </div>
  );
}
