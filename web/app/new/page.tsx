import Link from "next/link";
import { createSyntheticDocument } from "./actions";

const STATES = [
  "Delaware",
  "New York",
  "California",
  "Texas",
  "Illinois",
  "Massachusetts",
  "Washington",
  "Florida",
];

const DEFECTS: { value: string; label: string }[] = [
  { value: "missing_governing_law", label: "Omit the governing-law clause" },
  { value: "date_order", label: "Expiry date before the effective date" },
  { value: "missing_party_sig", label: "Drop one party's signature block" },
];

export default async function NewDocumentPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;

  return (
    <>
      <div className="detail-head">
        <h1>New NDA</h1>
        <Link href="/" className="button ghost">
          Back
        </Link>
      </div>
      <p className="detail-meta">
        Generate a synthetic NDA and run it through the pipeline. Leave a field
        blank to randomise it. Tick a defect to see validation catch it.
      </p>

      {error && <p className="form-error">{error}</p>}

      <form action={createSyntheticDocument} className="panel form">
        <div className="form-row">
          <label>
            Disclosing party
            <input name="disclosing_party" placeholder="(random)" />
          </label>
          <label>
            Receiving party
            <input name="receiving_party" placeholder="(random)" />
          </label>
        </div>

        <div className="form-row">
          <label>
            Effective date
            <input type="date" name="effective_date" />
          </label>
          <label>
            Term (years)
            <input type="number" name="term_years" min={1} max={20} placeholder="(random)" />
          </label>
        </div>

        <div className="form-row">
          <label>
            Direction
            <select name="agreement_type" defaultValue="">
              <option value="">Random</option>
              <option value="one-way">One-way</option>
              <option value="mutual">Mutual</option>
            </select>
          </label>
          <label>
            Governing law
            <select name="governing_law" defaultValue="">
              <option value="">Random</option>
              {STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        </div>

        <fieldset className="defects">
          <legend>Break it (optional)</legend>
          {DEFECTS.map((d) => (
            <label key={d.value} className="check">
              <input type="checkbox" name="violations" value={d.value} />
              {d.label}
            </label>
          ))}
        </fieldset>

        <button type="submit" className="button">
          Generate &amp; process
        </button>
      </form>
    </>
  );
}
