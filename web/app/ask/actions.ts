"use server";

import { API_BASE, TENANT_ID } from "@/app/lib/api";

export type Source = {
  n: number;
  document_id: string;
  filename: string;
  page: number;
  snippet: string;
};

export type AskState =
  | { status: "idle" }
  | { status: "error"; message: string }
  | { status: "ok"; question: string; answer: string; sources: Source[] };

export async function askAction(
  _prev: AskState,
  formData: FormData,
): Promise<AskState> {
  const question = String(formData.get("question") ?? "").trim();
  const documentId = String(formData.get("document_id") ?? "").trim() || null;

  if (!question) return { status: "error", message: "Enter a question." };

  const res = await fetch(`${API_BASE}/v1/ask`, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Tenant-Id": TENANT_ID },
    body: JSON.stringify({ question, document_id: documentId }),
    cache: "no-store",
  });

  if (!res.ok) {
    return { status: "error", message: `Ask failed (${res.status}).` };
  }

  const data = (await res.json()) as { answer: string; sources: Source[] };
  return { status: "ok", question, answer: data.answer, sources: data.sources };
}
