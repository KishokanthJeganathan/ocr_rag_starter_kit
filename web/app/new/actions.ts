"use server";

import { redirect } from "next/navigation";
import { API_BASE, MATTER_ID, TENANT_ID } from "@/app/lib/api";

export async function createSyntheticDocument(formData: FormData) {
  const field = (name: string) => {
    const v = formData.get(name);
    return typeof v === "string" && v.trim() !== "" ? v.trim() : undefined;
  };

  const body: Record<string, unknown> = { matter_id: MATTER_ID };
  const set = (key: string, value: unknown) => {
    if (value !== undefined) body[key] = value;
  };
  set("disclosing_party", field("disclosing_party"));
  set("receiving_party", field("receiving_party"));
  set("effective_date", field("effective_date"));
  const term = field("term_years");
  set("term_years", term ? Number(term) : undefined);
  set("agreement_type", field("agreement_type"));
  set("governing_law", field("governing_law"));
  const violations = formData
    .getAll("violations")
    .filter((v): v is string => typeof v === "string");
  if (violations.length) body.violations = violations;

  const res = await fetch(`${API_BASE}/v1/documents/synthetic`, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Tenant-Id": TENANT_ID },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (!res.ok) {
    const detail = await res.text();
    redirect(`/new?error=${encodeURIComponent(detail.slice(0, 240))}`);
  }

  const data = (await res.json()) as { document: { id: string } };
  redirect(`/documents/${data.document.id}`);
}
