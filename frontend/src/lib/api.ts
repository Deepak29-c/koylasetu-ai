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
  /** Why it failed, or that its original file is gone: translate with `failure.<code>`. The
   * raw exception text is never sent (#70). */
  failure_reason: string | null;
  failure_message: string | null;
  file_missing: boolean;
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
  id: string; // "C1" (passage) or "F1" (figure): the marker used inside the answer text
  kind: "passage" | "fact";
  document_id: string;
  document: string;
  page: number;
  bbox: number[] | null;
  text: string;
  chunk_id: string | null;
  fact_id: string | null;
  status: string | null;
};

export type AskResult = {
  qa_id: string;
  /** Only present when a past answer is reopened. */
  question?: string | null;
  answer: string;
  route: string;
  table: { columns: string[]; rows: string[][] } | null;
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

export type Fact = {
  id: string;
  metric: string;
  subsidiary: string | null;
  state: string | null;
  category: string | null;
  period_type: string | null;
  period: string | null;
  value_raw: string;
  value: number;
  unit: string | null;
  value_std: number | null;
  status: "EXTRACTED" | "FLAGGED" | "VERIFIED" | "REJECTED";
  confidence: number;
  document_id: string;
  page_no: number;
  bbox: number[] | null;
  label: string | null;
};

export type ReviewItem = {
  fact: Fact;
  document_title: string;
  issues: { id: string; rule_code: string; message: string; severity: "high" | "medium" | "low"; status: string }[];
  related: (Fact & { document_title: string })[];
  worst_severity: "high" | "medium" | "low";
  created_at: string;
};

/** A fact a reviewer already decided (GET /review/decided); posting again changes it. */
export type DecidedItem = Pick<ReviewItem, "fact" | "document_title" | "issues" | "related"> & {
  action: "ACCEPT" | "EDIT" | "REJECT";
  comment: string | null;
  decided_by: string;
  decided_at: string;
  decisions: number;
};

export type ReviewSummary = {
  total_facts: number;
  auto_verified: number;
  flagged: number;
  reviewed_verified: number;
  rejected: number;
  automation_percent: number | null;
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

export const AUDIT_PAGE_SIZE = 100;

export type AuditPage = { rows: AuditLogRow[]; hasMore: boolean };

/**
 * One page of the audit log. The backend has supported limit/offset all along.
 *
 * Asks for one row more than it shows: the API returns no total, and "a full page came
 * back" is not the same as "there is more" — when the count is an exact multiple of the
 * page size that would offer a Next leading to an empty page.
 */
export async function listAuditLog(filters: AuditFilters, offset = 0): Promise<AuditPage> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  params.set("limit", String(AUDIT_PAGE_SIZE + 1));
  params.set("offset", String(offset));
  const rows = await api<AuditLogRow[]>(`/audit?${params.toString()}`);
  return { rows: rows.slice(0, AUDIT_PAGE_SIZE), hasMore: rows.length > AUDIT_PAGE_SIZE };
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

/**
 * What a report holds. `text` is the plain rendering every report has; generated PQ replies
 * add header/blocks, monthly reports and briefing notes add title/sections. A save must send
 * the whole object back: the server replaces content_json as it is given.
 */
export type ReportContent = {
  text?: string;
  kind?: string;
  header?: Record<string, string>;
  blocks?: PqBlock[];
  title?: string;
  subtitle?: string;
  sections?: DraftSection[];
  /** PqSource[] or DraftSource[] depending on the kind; read it through a helper that checks. */
  sources?: unknown;
  warnings?: string[];
  remarks_by?: "model" | "rule";
  [key: string]: unknown;
};

export type ReportRow = {
  id: string;
  report_type: ReportType;
  title: string;
  status: ReportStatus;
  content_json: ReportContent;
  org_unit_id: string;
  created_by: string;
  approver_id: string | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
};

export type ReportVersionRow = {
  version: number;
  content_json: ReportContent;
  editor: { id: string; name: string; email: string };
  // What happened, as a code the page words in the reader's language (#71), and the human
  // comment exactly as typed. change_note is the old stored sentence, kept for history.
  change_kind: string | null;
  change_comment: string | null;
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
    /** A short code the screen can translate (`failure.<code>` in i18n), when there is one. */
    public code: string | null = null,
  ) {
    super(message);
  }
}

const UNREACHABLE = "Cannot reach the KoylaSetu server. Please check that the API is running.";
const UNREADABLE =
  "The KoylaSetu server is running, but its reply to this request could not be read. Please try again; if it keeps happening, tell the administrator.";

/**
 * A fetch that threw. That happens when the server is down - and also when it answered but
 * the browser would not let the page read the reply (an error response without CORS
 * headers). Saying "cannot reach the server" for the second sent people to check a server
 * that was running fine (#69), so ask /health before blaming it.
 */
async function unreachable(): Promise<ApiError> {
  try {
    const res = await fetch(`${API_URL}/health`);
    if (res.ok) return new ApiError(0, UNREADABLE, "unreadable_reply");
  } catch {}
  return new ApiError(0, UNREACHABLE, "unreachable");
}

// The API keeps the login in httpOnly cookies that page scripts cannot read, so nothing
// here ever sees a token. Every request sends the cookies (credentials: "include") and
// CSRF_HEADER, which the API requires on cookie-authenticated requests that change data.
const CSRF_HEADER = "X-Requested-With";
const CSRF_VALUE = "koylasetu";

// Not a token: only a note that this browser signed in, so that toLoginAgain can tell an
// ended session from a first visit. localStorage, like the cookies, is shared by every tab.
const SIGNED_IN = "ks_signed_in";

function signedIn(): boolean {
  try {
    return localStorage.getItem(SIGNED_IN) !== null;
  } catch {
    return false;
  }
}

function rememberSignedIn(): void {
  try {
    localStorage.setItem(SIGNED_IN, "1");
  } catch {}
}

function forgetSignedIn(): void {
  try {
    localStorage.removeItem(SIGNED_IN);
  } catch {}
}

// Tokens used to be kept in sessionStorage; drop any a tab still holds.
if (typeof window !== "undefined") {
  try {
    sessionStorage.removeItem("ks_access");
    sessionStorage.removeItem("ks_refresh");
  } catch {}
}

/** `init` with the login cookies and the CSRF header added. */
function withAuth(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers);
  headers.set(CSRF_HEADER, CSRF_VALUE);
  return { ...init, headers, credentials: "include" };
}

/** Ask the API to remove the login cookies. Callers then go to /login. */
export async function logout(): Promise<void> {
  forgetSignedIn();
  try {
    await fetch(`${API_URL}/auth/logout`, withAuth({ method: "POST" }));
  } catch {
    // server unreachable: the cookies expire on their own
  }
}

/** The server's own explanation of a failed response, with its translatable code if any. */
async function responseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const code = typeof body.code === "string" ? body.code : null;
    if (typeof body.detail === "string") return new ApiError(res.status, body.detail, code);
    if (Array.isArray(body.detail))
      return new ApiError(res.status, body.detail.map((d: { msg: string }) => d.msg).join("; "), code);
  } catch {}
  return new ApiError(res.status, `Request failed (${res.status})`);
}

// Several requests can 401 at once; they share one refresh call.
let refreshing: Promise<boolean> | null = null;

/** Swap the refresh cookie for new login cookies. */
function refreshTokens(): Promise<boolean> {
  refreshing ??= fetch(`${API_URL}/auth/refresh`, withAuth({ method: "POST" }))
    .then((res) => res.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/**
 * Send an expired session back to the login screen, remembering where they were.
 *
 * Handled here rather than in each page: every screen called `api()` and only AppShell's
 * first `/me` knew what a 401 meant, so everywhere else showed a dead red box with no way
 * back (#45).
 */
let leavingForLogin = false;

function toLoginAgain(): void {
  if (typeof window === "undefined") return;
  // Several requests can 401 at once (React re-invokes effects in development, and a
  // page often loads two things). Without this guard the first call forgets the session
  // and navigates to /login?next=…, then the second sees no session, decides nobody was
  // signed in, and navigates to a bare /login — aborting the first and losing `next`.
  if (leavingForLogin) return;
  leavingForLogin = true;
  const { pathname, search } = window.location;
  // Someone who never signed in is not resuming a session, they are just arriving.
  // Only a resumed session gets `next`, which is what makes the login page say "session ended".
  const hadSession = signedIn();
  forgetSignedIn();
  if (pathname === "/login") return; // already there; nothing to come back to
  const resuming = hadSession && pathname !== "/";
  // A full page load on purpose, not router.push: it drops every bit of in-memory state
  // left over from the expired session. This module is not a component, so there is no
  // router here anyway.
  window.location.assign(
    resuming ? `/login?next=${encodeURIComponent(pathname + search)}` : "/login",
  );
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, withAuth(init));
  } catch {
    throw await unreachable();
  }
  if (res.status === 401 && retry) {
    if (await refreshTokens()) return api<T>(path, init, false);
    toLoginAgain();
  }
  if (!res.ok) throw await responseError(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** Fetch an authenticated image (e.g. a page render) as an object URL for <img src>. */
export async function fetchImageUrl(path: string, retry = true): Promise<string> {
  const res = await fetch(`${API_URL}${path}`, withAuth());
  if (res.status === 401 && retry) {
    if (await refreshTokens()) return fetchImageUrl(path, false);
    toLoginAgain();
  }
  if (!res.ok) throw await responseError(res);
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
  content_json?: ReportContent;
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
  body: { title?: string; content_json?: ReportContent; due_date?: string | null; change_note?: string },
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

// --- PQ reply generator (guide 10.2) ---

export type PqSource = {
  id: string; // "S1": the marker used inside block text
  kind: "fact" | "chunk";
  fact_id: string | null;
  chunk_id: string | null;
  document_id: string;
  document: string;
  page: number;
  parts: string[];
};

export type PqBlock = {
  id: string;
  part: string; // "a", "b"… or "क"…; "" when the question has no parts
  question: string;
  text: string;
  table: { columns: string[]; rows: string[][] } | null;
  annexure: string | null; // "Annexure-I" when the table is moved to an annexure
  citations: string[];
  not_found: boolean;
  removed_numbers: string[];
  note: string | null;
};

export type PqDraftIn = {
  house: "LS" | "RS";
  q_type: "starred" | "unstarred";
  q_no?: string | null;
  answer_date?: string | null;
  mp_name?: string | null;
  subject?: string | null;
  question_text: string;
  /** When the reply has to be ready; the server uses the answer date when it is empty. */
  due_date?: string | null;
};

export type PqDraftOut = {
  pq_id: string;
  split_method: "markers" | "llm" | "single";
  report: ReportRow & {
    content_json: {
      text?: string;
      blocks?: PqBlock[];
      sources?: PqSource[];
      header?: Record<string, string>;
      warnings?: string[];
    };
  };
};

/** Generation takes minutes. The same idempotencyKey on a retry (e.g. after a proxy timeout)
 * returns the draft already made instead of creating a second one. */
export function draftPqReply(body: PqDraftIn, idempotencyKey: string): Promise<PqDraftOut> {
  return api<PqDraftOut>("/pq-replies/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(body),
  });
}

// --- Monthly report and briefing note drafts (guide 10.1, W5 / W6) ---

export type DraftSource = {
  id: string; // "S1": one document page; the marker used in lines and table cells
  document_id: string;
  document: string;
  page: number;
};

export type DraftSection = {
  id: string;
  heading: string | null;
  lines: string[];
  bullets: boolean;
  table: { columns: string[]; rows: string[][] } | null;
  notes: string[];
  removed_numbers: string[];
};

export type ReportDraftOut = {
  report: ReportRow & {
    content_json: {
      text?: string;
      kind?: "monthly" | "briefing";
      title?: string;
      subtitle?: string;
      sections?: DraftSection[];
      sources?: DraftSource[];
      warnings?: string[];
      remarks_by?: "model" | "rule";
    };
  };
};

function postDraft(path: string, body: object, idempotencyKey: string): Promise<ReportDraftOut> {
  return api<ReportDraftOut>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(body),
  });
}

export function draftMonthlyReport(month: string, idempotencyKey: string): Promise<ReportDraftOut> {
  return postDraft("/reports/monthly/draft", { month }, idempotencyKey);
}

export function draftBriefingNote(
  body: { topic: string; from?: string | null; to?: string | null },
  idempotencyKey: string,
): Promise<ReportDraftOut> {
  return postDraft("/reports/briefing/draft", body, idempotencyKey);
}

/** Download an authenticated file (e.g. a DOCX export) and hand it to the browser to save. */
/** The filename the server asked for, falling back to ours if it did not say. */
function serverFilename(res: Response, fallback: string): string {
  const disposition = res.headers.get("content-disposition") ?? "";
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1]);
    } catch {
      // malformed encoding: fall through to the plain form
    }
  }
  const plain = /filename="([^"]+)"/i.exec(disposition) ?? /filename=([^;]+)/i.exec(disposition);
  return plain ? plain[1].trim() : fallback;
}

export async function downloadFile(path: string, filename: string, retry = true): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, withAuth());
  } catch {
    throw await unreachable();
  }
  if (res.status === 401 && retry && (await refreshTokens())) return downloadFile(path, filename, false);
  if (!res.ok) throw await responseError(res);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = serverFilename(res, filename);
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

// The server names the file after the report's own type; `prefix` is only the fallback
// for when Content-Disposition cannot be read.
export function exportReport(id: string, format: "docx" | "pdf", prefix = "report"): Promise<void> {
  return downloadFile(`/reports/${id}/export?format=${format}`, `${prefix}-${id.slice(0, 8)}.${format}`);
}

export type QaHistoryRow = {
  id: string;
  question: string;
  route: string | null;
  grounded: boolean | null;
  created_at: string;
};

/** Questions this person asked, newest first. Only ever their own. */
export function listQaHistory(limit = 20): Promise<QaHistoryRow[]> {
  return api<QaHistoryRow[]>(`/qa/history?limit=${limit}`);
}

/** A past answer, rebuilt from its log. Nothing is re-asked and no model runs. */
export function getQaAnswer(id: string): Promise<AskResult> {
  return api<AskResult>(`/qa/${id}`);
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return api<DashboardSummary>("/dashboard/summary");
}

export async function login(email: string, password: string): Promise<void> {
  // The reply sets the login cookies; the tokens in its body are for scripts and are not kept.
  let res: Response;
  try {
    res = await fetch(
      `${API_URL}/auth/login`,
      withAuth({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      }),
    );
  } catch {
    throw await unreachable();
  }
  if (!res.ok) throw await responseError(res);
  rememberSignedIn();
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
    xhr.withCredentials = true;
    xhr.setRequestHeader(CSRF_HEADER, CSRF_VALUE);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onerror = () => {
      unreachable().then(reject);
    };
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
        const { detail, code } = (body ?? {}) as { detail?: unknown; code?: unknown };
        reject(
          new ApiError(
            xhr.status,
            typeof detail === "string" ? detail : "Upload failed",
            typeof code === "string" ? code : null,
          ),
        );
      }
    };
    xhr.send(form);
  });
}

// --- Metrics screen (guide 12 / 15.2) ---

export type MetricsOut = {
  qa: {
    questions_total: number;
    questions_this_month: number;
    grounded: number;
    grounded_pct: number | null;
    avg_latency_ms: number | null;
    helpful: number;
    not_helpful: number;
    helpful_pct: number | null;
  };
  facts: {
    total: number;
    auto_verified: number;
    reviewed_verified: number;
    flagged: number;
    rejected: number;
    automation_pct: number | null;
  };
  reports: { total: number; drafts: number; in_review: number; approved: number };
  /** Latest eval/run_eval.py run; null until the benchmark has been run on this machine. */
  benchmark: {
    run_date: string;
    questions_asked: number;
    answered: number;
    not_found: number;
    errors: number;
    numeric_accuracy_pct: number | null;
    all_correct_pct: number | null;
    grounded_pct: number | null;
    median_latency_ms: number | null;
    time_saved_pct: number | null;
    citation_correct_pct: number | null;
    automation_pct: number | null;
  } | null;
};

export function getMetrics(): Promise<MetricsOut> {
  return api<MetricsOut>("/metrics");
}
