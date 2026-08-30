"use client";

import Link from "next/link";
import { useActionState } from "react";
import { askAction, type AskState } from "./actions";

const INITIAL: AskState = { status: "idle" };

export function AskBox({
  documentId,
  placeholder = "Ask a question…",
}: {
  documentId?: string;
  placeholder?: string;
}) {
  const [state, action, pending] = useActionState(askAction, INITIAL);

  return (
    <div className="askbox">
      <form action={action} className="ask-form">
        {documentId && (
          <input type="hidden" name="document_id" value={documentId} />
        )}
        <input
          name="question"
          placeholder={placeholder}
          autoComplete="off"
          aria-label="Question"
        />
        <button type="submit" className="button" disabled={pending}>
          {pending ? "Asking…" : "Ask"}
        </button>
      </form>

      {state.status === "error" && (
        <p className="form-error">{state.message}</p>
      )}

      {state.status === "ok" && (
        <div className="ask-answer">
          <p className="ask-answer-text">{state.answer}</p>
          {state.sources.length > 0 && (
            <ol className="ask-sources">
              {state.sources.map((s) => (
                <li key={s.n}>
                  <Link href={`/documents/${s.document_id}`}>
                    [S{s.n}] {s.filename} · p.{s.page}
                  </Link>
                  <span className="ask-snippet">{s.snippet}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
