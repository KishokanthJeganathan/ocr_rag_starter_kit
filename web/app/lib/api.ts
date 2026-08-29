// Thin typed wrapper over the backend. All calls run in Server Components, so
// there is no CORS and no client-side data library — just fetch().

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const TENANT_ID =
  process.env.NEXT_PUBLIC_TENANT_ID ?? "00000000-0000-0000-0000-000000000001";

const headers = { "X-Tenant-Id": TENANT_ID };

export type DocumentOut = {
  id: string;
  matter_id: string;
  original_filename: string;
  mime_type: string;
  source_format: string;
  byte_size: number;
  content_sha256: string;
  is_scanned: boolean | null;
  page_count: number | null;
  status: string;
  doc_type: string | null;
  doc_type_confidence: number | null;
  error: string | null;
  created_at: string;
};

export type Cell = {
  value: unknown;
  confidence: number;
  evidence: string | null;
};

export type Extraction = {
  document_id: string;
  schema: string;
  model: string;
  fields: Record<string, Cell>;
};

export type Issue = {
  rule: string;
  severity: "error" | "warning";
  field: string;
  message: string;
};

export type Validation = {
  document_id: string;
  verdict: "passed" | "needs_review";
  issues: Issue[];
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function getOrNull<T>(path: string): Promise<T | null> {
  const res = await fetch(`${API_BASE}${path}`, { headers, cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const listDocuments = () => get<DocumentOut[]>("/v1/documents");
export const getDocument = (id: string) => get<DocumentOut>(`/v1/documents/${id}`);
export const getExtraction = (id: string) =>
  getOrNull<Extraction>(`/v1/documents/${id}/extraction`);
export const getValidation = (id: string) =>
  getOrNull<Validation>(`/v1/documents/${id}/validation`);

// Goes through the Next route handler (app/documents/[id]/pages/[page]/route.ts)
// so the tenant header stays server-side and <img> stays same-origin.
export const pageImageUrl = (id: string, page: number) =>
  `/documents/${id}/pages/${page}`;
