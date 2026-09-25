// The main menu as data, and which entries a user's permissions show. Kept free of React and
// runtime imports so `npm test` can check it per role; the icons are picked in AppShell.

import type { LabelKey } from "@/lib/i18n";
import type { Permission } from "@/lib/permissions";

export type NavItem = {
  href: string;
  label: LabelKey;
  /** Shown when the user holds any one of these; null means everyone. */
  needs: Permission[] | null;
  /** Indented under the item before it. */
  sub?: boolean;
};
export type NavGroup = { label?: LabelKey; items: NavItem[] };

// Menu shows only what the user's role can open (the API checks again on every request).
export const NAV_GROUPS: NavGroup[] = [
  { items: [{ href: "/", label: "home", needs: null }] },
  {
    label: "nav.work",
    items: [
      { href: "/ask", label: "ask", needs: ["ask_questions"] },
      // Same rule as canSeeReports in permissions.ts.
      { href: "/reports", label: "reports", needs: ["edit_reports", "approve_reports", "export_reports"] },
      { href: "/approvals", label: "nav.approvals", needs: ["approve_reports"] },
      { href: "/pq-replies/new", label: "newPqReply", needs: ["edit_reports"], sub: true },
      { href: "/monthly-reports/new", label: "newMonthlyReport", needs: ["edit_reports"], sub: true },
      { href: "/briefing-notes/new", label: "newBriefingNote", needs: ["edit_reports"], sub: true },
    ],
  },
  {
    label: "nav.data",
    items: [
      { href: "/upload", label: "upload", needs: ["upload_documents"] },
      { href: "/documents", label: "documents", needs: ["view_processing"] },
      { href: "/review", label: "review", needs: ["review_facts"] },
    ],
  },
  {
    label: "nav.insights",
    items: [
      { href: "/topics", label: "topics", needs: ["view_topics"] },
      { href: "/metrics", label: "nav.metrics", needs: ["view_metrics"] },
    ],
  },
  {
    label: "nav.admin",
    items: [
      { href: "/admin/users", label: "users", needs: ["manage_admin"] },
      { href: "/admin/templates", label: "adminTemplates.title", needs: ["manage_admin"] },
      { href: "/admin/rules", label: "adminRules.title", needs: ["manage_admin"] },
      { href: "/admin/status", label: "adminStatus.title", needs: ["manage_admin"] },
      { href: "/audit", label: "auditLog", needs: ["view_audit"] },
    ],
  },
];

/** The groups and entries these permissions show; groups left empty are dropped. */
export function visibleNav(permissions: readonly string[]): NavGroup[] {
  return NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => i.needs === null || i.needs.some((p) => permissions.includes(p))),
  })).filter((g) => g.items.length > 0);
}

const ALL_HREFS = [...NAV_GROUPS.flatMap((g) => g.items.map((i) => i.href)), "/profile"];

/** The menu entry for a path: the longest matching prefix, so /reports/123 lights up Reports. */
export function activeHref(pathname: string): string | null {
  if (pathname === "/") return "/";
  const matches = ALL_HREFS.filter((h) => h !== "/" && (pathname === h || pathname.startsWith(`${h}/`)));
  return matches.sort((a, b) => b.length - a.length)[0] ?? null;
}
