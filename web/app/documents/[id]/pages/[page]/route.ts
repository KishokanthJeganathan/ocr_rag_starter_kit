// Streams a page PNG from the backend, adding the tenant header the browser
// can't send on a plain <img>. Same-origin, so no CORS.
import { API_BASE, TENANT_ID } from "@/app/lib/api";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string; page: string }> },
) {
  const { id, page } = await params;
  const res = await fetch(
    `${API_BASE}/v1/documents/${id}/pages/${page}.png`,
    { headers: { "X-Tenant-Id": TENANT_ID }, cache: "no-store" },
  );
  if (!res.ok || !res.body) {
    return new Response("no image", { status: res.status || 502 });
  }
  return new Response(res.body, { headers: { "content-type": "image/png" } });
}
