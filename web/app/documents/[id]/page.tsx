import { notFound } from "next/navigation";
import {
  getDocument,
  getExtraction,
  getValidation,
  pageImageUrl,
  type Cell,
} from "@/app/lib/api";

export const dynamic = "force-dynamic";

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const level = value >= 0.7 ? "high" : "low";
  return (
    <span className="conf">
      <span className={`conf-bar ${level}`}>
        <span style={{ width: `${pct}%` }} />
      </span>
      {pct}%
    </span>
  );
}

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const document = await getDocument(id).catch(() => null);
  if (!document) notFound();

  const [extraction, validation] = await Promise.all([
    getExtraction(id),
    getValidation(id),
  ]);

  const flagged = new Set((validation?.issues ?? []).map((i) => i.field));
  const pageCount = document.page_count ?? 0;

  return (
    <>
      <div className="detail-head">
        <h1>{document.original_filename}</h1>
        {validation && (
          <span className={`badge ${validation.verdict}`}>
            {validation.verdict === "passed" ? "passed" : "needs review"}
          </span>
        )}
      </div>
      <p className="detail-meta">
        {document.status}
        {document.doc_type && ` · ${document.doc_type}`}
        {document.doc_type_confidence != null &&
          ` (${Math.round(document.doc_type_confidence * 100)}%)`}
        {` · ${pageCount} page${pageCount === 1 ? "" : "s"}`}
        {` · ${new Date(document.created_at).toLocaleString()}`}
      </p>

      <div className="detail-grid">
        <div className="pages">
          {Array.from({ length: pageCount }, (_, i) => (
            <img
              key={i}
              src={pageImageUrl(id, i + 1)}
              alt={`Page ${i + 1}`}
              loading="lazy"
            />
          ))}
        </div>

        <div className="stack">
          <section>
            <h2>Fields</h2>
            {extraction ? (
              <table className="fields">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Value</th>
                    <th>Confidence</th>
                    <th>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(extraction.fields).map(([name, cell]) => {
                    const c = cell as Cell;
                    return (
                      <tr
                        key={name}
                        className={flagged.has(name) ? "flagged" : undefined}
                      >
                        <td className="field-name">{name}</td>
                        <td className="field-value">{formatValue(c.value)}</td>
                        <td>
                          <Confidence value={c.confidence} />
                        </td>
                        <td className="evidence">
                          {c.evidence ? `“${c.evidence}”` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <p className="empty">
                No extraction — not an NDA, or not processed yet.
              </p>
            )}
          </section>

          <section>
            <h2>Validation</h2>
            {validation ? (
              validation.issues.length === 0 ? (
                <p className="empty">No issues. Safe to auto-approve.</p>
              ) : (
                <ul className="issues">
                  {validation.issues.map((issue, i) => (
                    <li key={i}>
                      <span className={`chip ${issue.severity}`}>
                        {issue.severity}
                      </span>
                      <span className="issue-field">{issue.field}</span>
                      <span>{issue.message}</span>
                    </li>
                  ))}
                </ul>
              )
            ) : (
              <p className="empty">Nothing to validate.</p>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
