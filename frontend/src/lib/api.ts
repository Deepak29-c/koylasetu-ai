// Thin client for the FastAPI backend. The API contract lives at {API_URL}/docs.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Me = {
  id: string;
  name: string;
  email: string;
  roles: string[];
  org_unit: { id: string; code: string; name: string; type: string };
  permissions: string[];
};

export type DocType = "annual_report" | "coal_inventory" | "monthly_stats" | "pq_answer" | "other";
export type DocumentStatus = "UPLOADED" | "PROCESSING" | "PROCESSED" | "NEEDS_REVIEW" | "FAILED";

export type DocumentRow = {
  id: string;
  title: string;
  original_filename: string;
  doc_type: DocType;
  fy: string | null;
  is_public: boolean;
  language: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error_message: string | null;
  page_count: number | null;
  pages_done: number;
  created_at: string;
};

export type UploadResult = {
  filename: string;
  result: "created" | "duplicate" | "rejected";
  document: DocumentRow | null;
  queued: boolean;
  error: string | null;
};

export type Citation = {
  id: string; // "C1": the marker used inside the answer text
  chunk_id: string;
  document_id: string;
  document: string;
  page: number;
  bbox: number[] | null;
  text: string;
};

export type AskResult = {
  qa_id: string;
  answer: string;
  route: string;
  citations: Citation[];
  grounded: boolean;
  unmatched_numbers: string[];
  confidence: "high" | "medium" | "low";
  not_found: boolean;
  latency_ms: number;
};

export type PageData = {
  document_id: string;
  document_title: string;
  source_url: string | null;
  page_no: number;
  page_count: number | null;
  has_text_layer: boolean;
  ocr_used: boolean;
  ocr_confidence: number | null;
  width: number | null;
  height: number | null;
  image_url: string | null;
  chunks: { id: string; text: string; bbox: number[] | null; has_embedding: boolean }[];
  tables: { id: string; table_title: string | null; bbox: number[] | null; rows_json: string[][] }[];
};

export type AuditLogRow = {
  id: string;
  created_at: string;
  user: { id: string; name: string; email: string } | null;
  action: string;
  entity: string | null;
  entity_id: string | null;
  details_json: Record<string, unknown> | null;
  ip: string | null;
};

export type AuditFilters = {
  action?: string;
  entity?: string;
  user_email?: string;
  from_date?: string;
  to_date?: string;
};

export function listAuditLog(filters: AuditFilters): Promise<AuditLogRow[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const qs = params.toString();
  return api<AuditLogRow[]>(`/audit${qs ? `?${qs}` : ""}`);
}

export function listAuditActions(): Promise<string[]> {
  return api<string[]>("/audit/actions");
}

export type Role = "admin" | "operator" | "reviewer" | "analyst" | "approver" | "viewer";
export const ALL_ROLES: Role[] = ["admin", "operator", "reviewer", "analyst", "approver", "viewer"];

export type OrgUnitOut = { id: string; code: string; name: string; type: string };

export type UserRow = {
  id: string;
  name: string;
  email: string;
  roles: string[];
  org_unit: OrgUnitOut;
  is_active: boolean;
  created_at: string;
};

export type UserCreateIn = {
  name: string;
  email: string;
  password: string;
  roles: string[];
  org_unit_id: string;
};

export type UserUpdateIn = {
  name?: string;
  roles?: string[];
  org_unit_id?: string;
  is_active?: boolean;
};

export type ReportType = "pq_reply" | "monthly" | "briefing";
export type ReportStatus = "DRAFT" | "IN_REVIEW" | "RETURNED" | "APPROVED" | "EXPORTED";

export type ReportRow = {
  id: string;
  report_type: ReportType;
  title: string;
  status: ReportStatus;
  content_json: { text?: string };
  org_unit_id: string;
  created_by: string;
  approver_id: string | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
};

export type ReportVersionRow = {
  version: number;
  content_json: { text?: string };
  editor: { id: string; name: string; email: string };
  change_note: string | null;
  created_at: string;
};

export type ReportsPanel = {
  my_drafts: number;
  returned_to_me: number;
  awaiting_approval: number;
  due_soon: number;
  overdue: number;
};

export type DocumentsPanel = {
  processing: number;
  needs_review: number;
  failed: number;
  processed_this_month: number;
};

export type ReviewPanel = { pending_facts: number; flagged_facts: number };

export type ActivityPanel = { questions_this_month: number };

/** Panels the signed-in person has no permission for come back as null, not zero. */
export type DashboardSummary = {
  reports: ReportsPanel | null;
  documents: DocumentsPanel | null;
  review: ReviewPanel | null;
  activity: ActivityPanel | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Tokens live in sessionStorage for the prototype (cleared when the tab closes).
// TODO before deployment: move to httpOnly cookies set by the API.
const ACCESS = "ks_access";
const REFRESH = "ks_refresh";

function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function saveTokens(t: { access_token: string; refresh_token: string }) {
  try {
    sessionStorage.setItem(ACCESS, t.access_token);
    sessionStorage.setItem(REFRESH, t.refresh_token);
  } catch {
    // storage blocked: the user will simply be asked to log in again
  }
}

export function logout() {
  try {
    sessionStorage.removeItem(ACCESS);
    sessionStorage.removeItem(REFRESH);
  } catch {}
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {}
  return `Request failed (${res.status})`;
}

async function refreshTokens(): Promise<boolean> {
  const refresh_token = read(REFRESH);
  if (!refresh_token) return false;
  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
  });
  if (!res.ok) return false;
  saveTokens(await res.json());
  return true;
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  const token = read(ACCESS);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Cannot reach the KoylaSetu server. Please check that the API is running.");
  }
  if (res.status === 401 && retry && (await refreshTokens())) return api<T>(path, init, false);
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** Fetch an authenticated image (e.g. a page render) as an object URL for <img src>. */
export async function fetchImageUrl(path: string, retry = true): Promise<string> {
  const headers = new Headers();
  const token = read(ACCESS);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { headers });
  if (res.status === 401 && retry && (await refreshTokens())) return fetchImageUrl(path, false);
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  return URL.createObjectURL(await res.blob());
}

export function listOrgUnits(): Promise<OrgUnitOut[]> {
  return api<OrgUnitOut[]>("/org-units");
}

export function listUsers(): Promise<UserRow[]> {
  return api<UserRow[]>("/users");
}

export function createUser(body: UserCreateIn): Promise<UserRow> {
  return api<UserRow>("/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function updateUser(id: string, body: UserUpdateIn): Promise<UserRow> {
  return api<UserRow>(`/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function listReports(filters: { status?: string; report_type?: string } = {}): Promise<ReportRow[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const qs = params.toString();
  return api<ReportRow[]>(`/reports${qs ? `?${qs}` : ""}`);
}

export function createReport(body: {
  report_type: ReportType;
  title: string;
  content_json?: { text?: string };
  due_date?: string | null;
}): Promise<ReportRow> {
  return api<ReportRow>("/reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getReport(id: string): Promise<ReportRow> {
  return api<ReportRow>(`/reports/${id}`);
}

export function listReportVersions(id: string): Promise<ReportVersionRow[]> {
  return api<ReportVersionRow[]>(`/reports/${id}/versions`);
}

export function updateReport(
  id: string,
  body: { title?: string; content_json?: { text?: string }; due_date?: string | null; change_note?: string },
): Promise<ReportRow> {
  return api<ReportRow>(`/reports/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function submitReport(id: string): Promise<ReportRow> {
  return api<ReportRow>(`/reports/${id}/submit`, { method: "POST" });
}

export function approveReport(id: string): Promise<ReportRow> {
  return api<ReportRow>(`/reports/${id}/approve`, { method: "POST" });
}

export function rejectReport(id: string, comment: string): Promise<ReportRow> {
  return api<ReportRow>(`/reports/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comment }),
  });
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return api<DashboardSummary>("/dashboard/summary");
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  saveTokens(await res.json());
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await api<void>("/me/password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

/** Multipart upload with a progress callback (fetch cannot report upload progress). */
export function uploadDocuments(
  form: FormData,
  onProgress: (fraction: number) => void,
  retry = true,
): Promise<UploadResult[]> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/documents`);
    const token = read(ACCESS);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onerror = () =>
      reject(new ApiError(0, "Cannot reach the KoylaSetu server. Please check that the API is running."));
    xhr.onload = async () => {
      if (xhr.status === 401 && retry && (await refreshTokens())) {
        uploadDocuments(form, onProgress, false).then(resolve, reject);
        return;
      }
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as UploadResult[]);
      else {
        const detail = (body as { detail?: unknown })?.detail;
        reject(new ApiError(xhr.status, typeof detail === "string" ? detail : "Upload failed"));
      }
    };
    xhr.send(form);
  });
}
