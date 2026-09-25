import type { Me } from "@/lib/api";

/** Permission names as the API sends them in /me (backend app/core/rbac.py). */
export type Permission =
  | "manage_admin"
  | "upload_documents"
  | "view_processing"
  | "review_facts"
  | "ask_questions"
  | "edit_reports"
  | "approve_reports"
  | "export_reports"
  | "view_topics"
  | "view_audit"
  | "view_metrics";

/** True when the user holds any of the permissions. The API checks again on every call. */
export function can(me: Pick<Me, "permissions"> | null | undefined, ...perms: Permission[]): boolean {
  return !!me && perms.some((p) => me.permissions.includes(p));
}

export function canSeeReports(me: Pick<Me, "permissions"> | null | undefined): boolean {
  return can(me, "edit_reports", "approve_reports", "export_reports");
}
