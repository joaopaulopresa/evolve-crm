import { type FormEvent, useState } from "react";

import { api } from "../api";
import { useAuth } from "../auth";
import type { AskAnswer, AskQuery, Features } from "../types";
import { useLoad } from "../useLoad";

const EXAMPLES = [
  "Which salesperson closed the most in the last quarter, and what was the average deal size?",
  "Which open deals have had no activity in the last 30 days?",
  "How much is in each pipeline stage right now?",
];

type Turn = { question: string; answer?: AskAnswer; error?: string };

const cell = (value: unknown) =>
  typeof value === "number"
    ? value.toLocaleString("en-US", { maximumFractionDigits: 2 })
    : value === null
      ? ""
      : String(value);

function ResultTable({ query }: { query: AskQuery }) {
  if (query.columns.length === 0 || query.rows.length === 0) return null;
  return (
    <div className="result">
      <table className="table">
        <thead>
          <tr>
            {query.columns.map((column) => (
              <th key={column}>{column.replaceAll("_", " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {query.rows.slice(0, 20).map((row, index) => (
            <tr key={index}>
              {row.map((value, column) => (
                <td key={column} className={typeof value === "number" ? "number" : ""}>
                  {cell(value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {query.row_count > 20 && <p className="muted">Showing 20 of {query.row_count} rows.</p>}
    </div>
  );
}

export function Ask() {
  const { user } = useAuth();
  const features = useLoad(() => api<Features>("/features"), []);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [conversation, setConversation] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function ask(text: string) {
    setBusy(true);
    setQuestion("");
    setTurns((previous) => [...previous, { question: text }]);
    const finish = (result: Partial<Turn>) =>
      setTurns((previous) => [...previous.slice(0, -1), { question: text, ...result }]);
    try {
      const answer = await api<AskAnswer>("/ask", {
        method: "POST",
        body: { question: text, conversation_id: conversation },
      });
      setConversation(answer.conversation_id);
      finish({ answer });
    } catch (reason) {
      finish({ error: (reason as Error).message });
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (question.trim()) void ask(question.trim());
  }

  const off = features.data && !features.data.ask;

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Ask</h1>
          <p className="muted">
            Ask about the data in plain language.{" "}
            {user!.role === "admin"
              ? "You see everyone's records."
              : "Answers only use the records you can see."}
          </p>
        </div>
      </header>

      {off ? (
        <p className="empty">
          {features.data!.ask_disabled_by_owner
            ? "Questions about the data are switched off for this installation."
            : `This copy of the CRM (${features.data!.environment}) is not connected to the analyst. Use the production environment.`}
        </p>
      ) : (
        <div className="ask">
          <ol className="turns">
            {turns.map((turn, index) => {
              const shown = turn.answer?.queries.filter((query) => !query.error).at(-1);
              return (
                <li key={index} className="turn">
                  <p className="question">{turn.question}</p>
                  {!turn.answer && !turn.error && <p className="muted">Looking at the data…</p>}
                  {turn.error && (
                    <p className="form-error" role="alert">
                      {turn.error}
                    </p>
                  )}
                  {turn.answer && (
                    <div className="answer" data-testid="answer">
                      <p className="chat-text">{turn.answer.answer}</p>
                      {shown && <ResultTable query={shown} />}
                      {turn.answer.queries.length > 0 && (
                        <details>
                          <summary>
                            Show the SQL ({turn.answer.queries.length}{" "}
                            {turn.answer.queries.length === 1 ? "query" : "queries"})
                          </summary>
                          {turn.answer.queries.map((query, number) => (
                            <pre key={number} className="log sql">
                              {query.sql}
                              {query.error && `\n-- failed: ${query.error}`}
                            </pre>
                          ))}
                        </details>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>

          {turns.length === 0 && (
            <div className="examples">
              {EXAMPLES.map((example) => (
                <button key={example} type="button" className="chip" onClick={() => ask(example)}>
                  {example}
                </button>
              ))}
            </div>
          )}

          <form className="ask-form" onSubmit={submit}>
            <input
              aria-label="Your question"
              placeholder="Ask a question about your companies, contacts, deals or activities"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              disabled={busy}
            />
            <button type="submit" className="button primary" disabled={busy}>
              {busy ? "Asking…" : "Ask"}
            </button>
          </form>
          <p className="muted fine-print">
            Your question, the table layout and the query results are sent to the language model
            provider to write the answer.
          </p>
        </div>
      )}
    </>
  );
}
