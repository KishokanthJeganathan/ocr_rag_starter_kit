import Link from "next/link";
import { listDocuments, getValidation, type Validation } from "./lib/api";

export const dynamic = "force-dynamic";

export default async function DocumentListPage() {
  const documents = await listDocuments();
  const validations = await Promise.all(
    documents.map((d) => getValidation(d.id)),
  );
  const verdictById = new Map<string, Validation | null>(
    documents.map((d, i) => [d.id, validations[i]]),
  );

  return (
    <>
      <div className="detail-head">
        <h1>Documents</h1>
        <Link href="/new" className="button">
          New NDA
        </Link>
      </div>
      {documents.length === 0 ? (
        <p className="empty">
          Nothing here yet. Create one with <strong>New NDA</strong>, or run{" "}
          <code>make try-ocr F=…</code>.
        </p>
      ) : (
        <table className="doc-table">
          <thead>
            <tr>
              <th>File</th>
              <th>Status</th>
              <th>Type</th>
              <th>Verdict</th>
              <th>Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => {
              const v = verdictById.get(d.id) ?? null;
              return (
                <tr key={d.id}>
                  <td>
                    <Link href={`/documents/${d.id}`} className="filename">
                      {d.original_filename}
                    </Link>
                  </td>
                  <td>{d.status}</td>
                  <td>{d.doc_type ?? "—"}</td>
                  <td>
                    {v ? (
                      <span className={`badge ${v.verdict}`}>
                        {v.verdict === "passed"
                          ? "passed"
                          : `needs review (${v.issues.length})`}
                      </span>
                    ) : (
                      <span className="badge muted">—</span>
                    )}
                  </td>
                  <td>{new Date(d.created_at).toLocaleString()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
}
