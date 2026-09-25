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

export type DocumentDetail = DocumentRow & {
  org_unit_id: string;
  source_url: string | null;
};

export type ChunkOut = {
  id: string;
  text: string;
  bbox: [number, number, number, number] | null;
  has_embedding: boolean;
};

export type TableOut = {
  id: string;
  table_title: string | null;
  bbox: [number, number, number, number] | null;
  rows_json: string[][];
};

export type PageOut = {
  document_id: string;
  page_no: number;
  page_count: number | null;
  has_text_layer: boolean;
  ocr_used: boolean;
  ocr_confidence: number | null;
  width: number | null;
  height: number | null;
  image_url: string | null;
  chunks: ChunkOut[];
  tables: TableOut[];
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
  return res.json() as Promise<T>;
}

export function getDocument(id: string): Promise<DocumentDetail> {
  return api<DocumentDetail>(`/documents/${id}`);
}

export function getPage(id: string, pageNo: number): Promise<PageOut> {
  return api<PageOut>(`/documents/${id}/pages/${pageNo}`);
}

/** The page image needs the auth header, so a plain <img src> can't fetch it directly —
 * this loads it and hands back a local blob URL. Caller must revokeObjectURL when done. */
export async function fetchPageImage(imageUrl: string): Promise<string> {
  const headers = new Headers();
  const token = read(ACCESS);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${imageUrl}`, { headers });
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  return URL.createObjectURL(await res.blob());
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
