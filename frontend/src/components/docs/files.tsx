import { File as FileGeneric, FileImage, FileSpreadsheet, FileText } from "lucide-react";

import { formatNumber } from "@/lib/format";

/** File types the server accepts, and the upload size limit. */
export const ACCEPTED_EXTENSIONS = ["pdf", "xlsx", "xls", "csv", "png", "jpg", "jpeg", "tif", "tiff", "docx"];
export const ACCEPT = ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(",");
export const MAX_BYTES = 100 * 1024 * 1024;

export type FileIssue = "tooLarge" | "unsupported";

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
}

/** Why a file would be refused by the server, or null when it looks fine. */
export function fileIssue(f: File): FileIssue | null {
  if (!ACCEPTED_EXTENSIONS.includes(extensionOf(f.name))) return "unsupported";
  if (f.size > MAX_BYTES) return "tooLarge";
  return null;
}

export function fileKey(f: File): string {
  return `${f.name}:${f.size}:${f.lastModified}`;
}

/** Size in KB or MB; unit labels come from the caller so they follow the UI language. */
export function formatSize(bytes: number, locale: string, units: { kb: string; mb: string }): string {
  if (bytes < 1024 * 1024) return `${formatNumber(Math.max(1, Math.round(bytes / 1024)), locale)} ${units.kb}`;
  return `${formatNumber(bytes / (1024 * 1024), locale, 1)} ${units.mb}`;
}

export function FileTypeIcon({ name, size = 20, className }: { name: string; size?: number; className?: string }) {
  const ext = extensionOf(name);
  const Icon = ["xlsx", "xls", "csv"].includes(ext)
    ? FileSpreadsheet
    : ["png", "jpg", "jpeg", "tif", "tiff"].includes(ext)
      ? FileImage
      : ["pdf", "docx"].includes(ext)
        ? FileText
        : FileGeneric;
  return <Icon size={size} aria-hidden className={className} />;
}
