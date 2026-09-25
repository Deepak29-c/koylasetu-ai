"use client";

import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import { type AuditFilters, type AuditLogRow, listAuditActions, listAuditLog } from "@/lib/api";
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

  const load = useCallback(
    (f: AuditFilters) =>
      listAuditLog(f).then(
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
    load(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowed]);

  if (!allowed) return <p className="text-gray-600">{t("noPermission")}</p>;

  function applyFilters(next: AuditFilters) {
    setFilters(next);
    setRows(null);
    load(next);
  }

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
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="cursor-pointer border-t align-top hover:bg-gray-50">
                  <td
                    className="px-4 py-2 whitespace-nowrap"
                    onClick={() => setOpenId(openId === r.id ? null : r.id)}
                  >
                    {new Date(r.created_at).toLocaleString("en-IN")}
                  </td>
                  <td className="px-4 py-2" onClick={() => setOpenId(openId === r.id ? null : r.id)}>
                    {r.user ? (
                      <>
                        <div className="font-medium">{r.user.name}</div>
                        <div className="text-xs text-gray-500">{r.user.email}</div>
                      </>
                    ) : (
                      <span className="text-gray-400">{t("auditSystem")}</span>
                    )}
                  </td>
                  <td className="px-4 py-2" onClick={() => setOpenId(openId === r.id ? null : r.id)}>
                    <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium">
                      {r.action}
                    </span>
                  </td>
                  <td className="px-4 py-2" onClick={() => setOpenId(openId === r.id ? null : r.id)}>
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
                    {openId === r.id && r.details_json && (
                      <pre className="mt-1 max-w-md overflow-x-auto rounded bg-gray-50 p-2 text-xs text-gray-700">
                        {JSON.stringify(r.details_json, null, 2)}
                      </pre>
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-500">{r.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
