"use client";

import { Fragment, useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import {
  AUDIT_PAGE_SIZE,
  type AuditFilters,
  type AuditLogRow,
  listAuditActions,
  listAuditLog,
} from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function AuditLogPage() {
  const me = useMe();
  const { t } = useT();
  const allowed = me.permissions.includes("view_audit");

  const [rows, setRows] = useState<AuditLogRow[] | null>(null);
  const [actions, setActions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<AuditFilters>({});
  const [openId, setOpenId] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const load = useCallback(
    (f: AuditFilters, from: number) =>
      listAuditLog(f, from).then(
        (r) => {
          setRows(r);
          setError(null);
        },
        (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
      ),
    [],
  );

  useEffect(() => {
    if (!allowed) return;
    listAuditActions().then(setActions, () => {});
    load(filters, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowed]);

  if (!allowed) return <p className="text-gray-600">{t("noPermission")}</p>;

  function applyFilters(next: AuditFilters) {
    setFilters(next);
    setRows(null);
    setOffset(0); // a new filter starts a new list; page 3 of the old one is meaningless
    load(next, 0);
  }

  function goTo(from: number) {
    setOffset(from);
    setRows(null);
    setOpenId(null);
    load(filters, from);
    window.scrollTo({ top: 0 });
  }

  // A full page means there is probably more; the API returns no total.
  const maybeMore = rows !== null && rows.length === AUDIT_PAGE_SIZE;

  const hasFilters = Object.values(filters).some(Boolean);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t("auditLog")}</h1>

      <div className="flex flex-wrap items-end gap-3 rounded border bg-white p-3">
        <label className="block text-sm">
          <span className="font-medium">{t("auditFilterAction")}</span>
          <select
            value={filters.action ?? ""}
            onChange={(e) => applyFilters({ ...filters, action: e.target.value || undefined })}
            className="mt-1 block rounded border px-2 py-1.5"
          >
            <option value="">{t("auditAllActions")}</option>
            {actions.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-medium">{t("auditFilterUser")}</span>
          <input
            type="text"
            value={filters.user_email ?? ""}
            onChange={(e) => applyFilters({ ...filters, user_email: e.target.value || undefined })}
            className="mt-1 block rounded border px-2 py-1.5"
            placeholder="name@koylasetu.local"
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium">{t("auditFilterFrom")}</span>
          <input
            type="date"
            value={filters.from_date ?? ""}
            onChange={(e) => applyFilters({ ...filters, from_date: e.target.value || undefined })}
            className="mt-1 block rounded border px-2 py-1.5"
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium">{t("auditFilterTo")}</span>
          <input
            type="date"
            value={filters.to_date ?? ""}
            onChange={(e) => applyFilters({ ...filters, to_date: e.target.value || undefined })}
            className="mt-1 block rounded border px-2 py-1.5"
          />
        </label>
        {hasFilters && (
          <button onClick={() => applyFilters({})} className="text-sm text-brand underline">
            {t("auditClearFilters")}
          </button>
        )}
      </div>

      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
      {rows === null && !error && <p className="text-gray-500">{t("loading")}</p>}
      {rows?.length === 0 && <p className="text-gray-600">{t("auditNoResults")}</p>}
      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded border bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-2 font-medium">{t("auditWhen")}</th>
                <th className="px-4 py-2 font-medium">{t("auditWho")}</th>
                <th className="px-4 py-2 font-medium">{t("auditAction")}</th>
                <th className="px-4 py-2 font-medium">{t("auditWhat")}</th>
                <th className="px-4 py-2 font-medium">{t("auditIp")}</th>
                <th className="px-4 py-2 font-medium">{t("auditDetails")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.id}>
                  <tr className="border-t align-top hover:bg-gray-50">
                    <td className="px-4 py-2 whitespace-nowrap">
                      {new Date(r.created_at).toLocaleString("en-IN")}
                    </td>
                    <td className="px-4 py-2">
                      {r.user ? (
                        <>
                          <div className="font-medium">{r.user.name}</div>
                          <div className="text-xs text-gray-500">{r.user.email}</div>
                        </>
                      ) : (
                        <span className="text-gray-400">{t("auditSystem")}</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium">
                        {r.action}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      {r.entity ? (
                        r.entity === "document" && r.entity_id ? (
                          <a href={`/documents/${r.entity_id}`} className="text-brand underline">
                            {r.entity} · {r.entity_id.slice(0, 8)}
                          </a>
                        ) : (
                          <>
                            {r.entity}
                            {r.entity_id ? ` · ${r.entity_id.slice(0, 8)}` : ""}
                          </>
                        )
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-2 text-gray-500">{r.ip ?? "—"}</td>
                    <td className="px-4 py-2">
                      {r.details_json ? (
                        <button
                          aria-expanded={openId === r.id}
                          onClick={() => setOpenId(openId === r.id ? null : r.id)}
                          className="text-xs text-brand underline"
                        >
                          {t("auditDetails")}
                        </button>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                  </tr>
                  {openId === r.id && r.details_json && (
                    <tr>
                      <td colSpan={6} className="px-4 pb-3">
                        <pre className="overflow-x-auto rounded bg-gray-50 p-2 text-xs text-gray-700">
                          {JSON.stringify(r.details_json, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-gray-600">
            {t("audit.showing")} {offset + 1}–{offset + rows.length}
          </span>
          <button
            onClick={() => goTo(Math.max(0, offset - AUDIT_PAGE_SIZE))}
            disabled={offset === 0}
            className="rounded border px-3 py-1 disabled:text-gray-400"
          >
            {t("prev")}
          </button>
          <button
            onClick={() => goTo(offset + AUDIT_PAGE_SIZE)}
            disabled={!maybeMore}
            className="rounded border px-3 py-1 disabled:text-gray-400"
          >
            {t("next")}
          </button>
          {maybeMore && <span className="text-gray-500">{t("audit.moreAvailable")}</span>}
        </div>
      )}
    </div>
  );
}
