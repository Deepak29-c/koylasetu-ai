"use client";

import Link from "next/link";

import { useMe } from "@/components/AppShell";
import { useT } from "@/lib/i18n";

// Placeholder home. The real dashboard (pending tasks, quick Ask box, metrics) comes later.
export default function HomePage() {
  const me = useMe();
  const { t } = useT();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">
          {t("welcome")}, {me.name}
        </h1>
        <p className="text-gray-600">{t("tagline")}</p>
      </div>
      <dl className="grid max-w-xl grid-cols-[max-content_1fr] gap-x-6 gap-y-2 rounded border bg-white p-4">
        <dt className="text-gray-500">{t("yourRoles")}</dt>
        <dd className="capitalize">{me.roles.join(", ")}</dd>
        <dt className="text-gray-500">{t("yourUnit")}</dt>
        <dd>
          {me.org_unit.name} ({me.org_unit.code})
        </dd>
      </dl>
      <div className="flex gap-3">
        {me.permissions.includes("upload_documents") && (
          <Link href="/upload" className="rounded bg-brand px-4 py-2 font-medium text-white">
            {t("uploadTitle")}
          </Link>
        )}
        {me.permissions.includes("view_processing") && (
          <Link href="/documents" className="rounded border border-brand px-4 py-2 text-brand">
            {t("documents")}
          </Link>
        )}
      </div>
    </div>
  );
}
