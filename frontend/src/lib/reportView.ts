// Small pure rules for the report screen, kept out of the page so they can be tested
// without a browser (`npm test`). Type-only imports: this file must not pull in runtime code.

import type { ReportStatus, ReportVersionRow } from "@/lib/api";

export const EDITABLE_STATUSES: ReportStatus[] = ["DRAFT", "RETURNED"];

/**
 * How the Content section should look for this person (#64).
 *
 * - "edit": they can edit and the status allows it.
 * - "status_blocked": they could edit, but not at this status. Telling them the status is
 *   the true reason, so the page keeps its "can't be edited right now" message.
 * - "read_only": they can't edit reports at all (a Viewer, an Approver). No editing box
 *   and no status excuse - the status was never the reason.
 */
export type ContentMode = "edit" | "status_blocked" | "read_only";

export function contentMode(canEdit: boolean, status: ReportStatus): ContentMode {
  if (!canEdit) return "read_only";
  return EDITABLE_STATUSES.includes(status) ? "edit" : "status_blocked";
}

export const VERSION_KINDS = [
  "created",
  "drafted",
  "drafted_from_question",
  "edited",
  "approved",
  "returned",
] as const;
export type VersionKind = (typeof VERSION_KINDS)[number];

/**
 * One version-history line as a translatable code plus the human comment (#71).
 *
 * `kind` is null only when the server sent a code this build doesn't know; the page then
 * shows the stored sentence (`fallback`) as it is rather than an empty line.
 * `comment` is the approver's or editor's own words and is never translated.
 */
export function versionLine(v: Pick<ReportVersionRow, "change_kind" | "change_comment" | "change_note">): {
  kind: VersionKind | null;
  comment: string | null;
  fallback: string | null;
} {
  const kind = (VERSION_KINDS as readonly string[]).includes(v.change_kind ?? "")
    ? (v.change_kind as VersionKind)
    : null;
  return {
    kind,
    comment: kind ? (v.change_comment ?? null) : null,
    fallback: kind ? null : (v.change_note ?? v.change_comment ?? null),
  };
}
