import Link from "next/link";
import { AskBox } from "./ask-box";

export const dynamic = "force-dynamic";

export default function AskPage() {
  return (
    <>
      <div className="detail-head">
        <h1>Ask across all documents</h1>
        <Link href="/" className="button ghost">
          Back
        </Link>
      </div>
      <p className="detail-meta">
        Answers are grounded only in the processed documents, with a citation to
        the page each fact came from.
      </p>
      <AskBox placeholder="e.g. Which agreements are governed by California law?" />
    </>
  );
}
