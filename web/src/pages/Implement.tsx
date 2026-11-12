import { type FormEvent, useEffect, useState } from "react";

import { api } from "../api";
import { day } from "../format";
import { buildTimeline, canReply, isBusy, isFinal, shortSha, STATUS_LABEL } from "../requests";
import type { ChangeRequest, Features, Releases, RequestEvent } from "../types";
import { useLoad } from "../useLoad";

const EXAMPLES = [
  "Add a 'lead source' field to contacts, with a filter for it on the contacts page.",
  "Show the number of open deals next to each company in the companies list.",
  "Add a 'priority' (low, medium, high) to deals and show it on the pipeline cards.",
];

function EventRow({ event }: { event: RequestEvent }) {
  const who =
    event.actor === "hermes" ? "Hermes" : event.actor === "pipeline" ? "Pipeline" : "You";
  const tone =
    event.kind.endsWith("failed") || event.kind === "agent_declined"
      ? "bad"
      : ["preview_ready", "deployed", "approved"].includes(event.kind)
        ? "good"
        : "";
  const url = typeof event.data?.url === "string" ? event.data.url : null;
  return (
    <li className={`chat-item from-${who.toLowerCase()} ${tone}`}>
      <span className="chat-who">{who}</span>
      <div className="chat-body">
        {event.kind === "approved" && <p>Approved. Merging and deploying to production.</p>}
        {event.kind === "discarded" && <p>Discarded this change.</p>}
        {event.message && <p className="chat-text">{event.message}</p>}
        {url && event.kind === "preview_ready" && (
          <p>
            <a className="text-link" href={url} target="_blank" rel="noreferrer">
              Try it here: {url}
            </a>
          </p>
        )}
        {event.log && (
          <details>
            <summary>Show the log</summary>
            <pre className="log">{event.log}</pre>
          </details>
        )}
      </div>
    </li>
  );
}

function RequestView({ id, onChanged }: { id: number; onChanged: () => void }) {
  const [request, setRequest] = useState<ChangeRequest | null>(null);
  const [reply, setReply] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const next = await api<ChangeRequest>(`/change-requests/${id}`);
        if (stopped) return;
        setRequest((previous) => {
          if (previous && previous.status !== next.status) onChanged();
          return next;
        });
        // Production restarts while it deploys this very change; keep trying.
        timer = setTimeout(load, isFinal(next.status) ? 15000 : 2000);
      } catch {
        if (!stopped) timer = setTimeout(load, 3000);
      }
    };
    setRequest(null);
    void load();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function act(path: string, body?: unknown) {
    setError(null);
    try {
      setRequest({ ...(await api<ChangeRequest>(path, { method: "POST", body })), events: request?.events });
      onChanged();
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    await act(`/change-requests/${id}/messages`, { text: reply });
    setReply("");
  }

  if (!request) return <p className="muted">Loading…</p>;
  const timeline = buildTimeline(request.events ?? []);
  const busy = isBusy(request.status);

  return (
    <section className="panel request" aria-label={`Change request ${request.id}`}>
      <header className="request-header">
        <div>
          <h2>{request.title}</h2>
          <p className="muted">
            Request #{request.id} by {request.requested_by_name}, {day(request.created_at)}
          </p>
        </div>
        <span className={`status status-${request.status}`} data-testid="request-status">
          {STATUS_LABEL[request.status]}
        </span>
      </header>

      <ol className="chat">
        {timeline.map((item) =>
          item.type === "event" ? (
            <EventRow key={item.event.id} event={item.event} />
          ) : (
            <li key={`steps-${item.id}`} className="chat-item from-hermes">
              <span className="chat-who">Hermes</span>
              <details className="steps" open={busy}>
                <summary>
                  {item.steps.length} {item.steps.length === 1 ? "step" : "steps"} in the sandbox
                </summary>
                <ul>
                  {item.steps.map((step) => (
                    <li key={step.id}>{step.message}</li>
                  ))}
                </ul>
              </details>
            </li>
          ),
        )}
        {busy && (
          <li className="chat-item from-pipeline working" aria-live="polite">
            <span className="chat-who" />
            <p className="muted">{STATUS_LABEL[request.status]}…</p>
          </li>
        )}
      </ol>

      {request.status === "preview_ready" && request.preview_url && (
        <div className="preview-bar">
          <div>
            <strong>The change is running in a preview with demo data.</strong>
            <a className="text-link" href={request.preview_url} target="_blank" rel="noreferrer">
              Open the preview: {request.preview_url}
            </a>
          </div>
          <button
            type="button"
            className="button primary"
            onClick={() => act(`/change-requests/${id}/approve`)}
          >
            Approve and deploy
          </button>
        </div>
      )}

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {canReply(request.status) && (
        <form className="reply" onSubmit={send}>
          <label className="field">
            <span>
              {request.status === "preview_ready"
                ? "Ask Hermes for an adjustment"
                : "Reply to Hermes"}
            </span>
            <textarea
              rows={2}
              value={reply}
              onChange={(event) => setReply(event.target.value)}
              required
            />
          </label>
          <footer className="form-actions">
            <button
              type="button"
              className="button danger"
              onClick={() => act(`/change-requests/${id}/discard`)}
            >
              Discard this change
            </button>
            <button type="submit" className="button">
              Send to Hermes
            </button>
          </footer>
        </form>
      )}

      <footer className="request-meta muted">
        {request.head_sha && <span>Commit {shortSha(request.head_sha)}</span>}
        {request.tokens > 0 && (
          <span>
            {request.tokens.toLocaleString("en-US")} tokens
            {request.cost_usd != null && `, about $${request.cost_usd.toFixed(4)}`}
          </span>
        )}
        {request.trace_url && (
          <a className="text-link" href={request.trace_url} target="_blank" rel="noreferrer">
            Open the trace in Langfuse
          </a>
        )}
      </footer>
    </section>
  );
}

function ReleasePanel({ refreshKey }: { refreshKey: number }) {
  const releases = useLoad(() => api<Releases>("/releases"), [refreshKey]);
  const [message, setMessage] = useState<string | null>(null);
  // Deploys and rollbacks finish on their own time: keep the panel current.
  const { reload } = releases;
  useEffect(() => {
    const timer = setInterval(reload, 4000);
    return () => clearInterval(timer);
  }, [reload]);

  async function rollback() {
    if (!window.confirm("Switch production to the other release? Data is kept.")) return;
    try {
      await api("/releases/rollback", { method: "POST" });
      setMessage("Rolling back. Production restarts in a moment.");
    } catch (reason) {
      setMessage((reason as Error).message);
    }
  }

  const data = releases.data;
  // After a rollback, the release to go to is the newer one: say "restore", not "roll back".
  const lastGood = data?.history.filter((release) => release.ok).at(-1);
  const undoing = lastGood?.kind === "rollback";
  return (
    <section className="panel release">
      <h2>Production</h2>
      {data ? (
        <>
          <p>
            Release <strong data-testid="current-release">{shortSha(data.current) || "none"}</strong>
          </p>
          <button
            type="button"
            className="button"
            disabled={!data.rollback_target || data.busy}
            onClick={rollback}
          >
            {undoing ? "Restore release" : "Roll back to"}{" "}
            {shortSha(data.rollback_target) || "previous"}
          </button>
          {message && <p className="muted">{message}</p>}
        </>
      ) : (
        <p className="muted">{releases.error ?? "Loading…"}</p>
      )}
    </section>
  );
}

export function Implement() {
  const features = useLoad(() => api<Features>("/features"), []);
  const [refreshKey, setRefreshKey] = useState(0);
  const requests = useLoad(() => api<ChangeRequest[]>("/change-requests"), [refreshKey]);
  const [selected, setSelected] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const refresh = () => setRefreshKey((key) => key + 1);

  const list = requests.data ?? [];
  const unfinished = list.find((request) => !isFinal(request.status));
  // Follow the request in progress, and keep it on screen after it finishes: going live is
  // the moment the owner most wants to see.
  useEffect(() => {
    if (selected === null && unfinished) setSelected(unfinished.id);
  }, [selected, unfinished]);
  const current = selected ?? unfinished?.id ?? null;

  async function open(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const created = await api<ChangeRequest>("/change-requests", {
        method: "POST",
        body: { description: text },
      });
      setText("");
      setSelected(created.id);
      refresh();
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  if (features.data && !features.data.implement) {
    return (
      <>
        <header className="page-header">
          <h1>Implement</h1>
        </header>
        <p className="empty">
          This copy of the CRM ({features.data.environment}) cannot change itself. Changes are
          requested from the production environment, where Hermes and the delivery pipeline are
          connected.
        </p>
      </>
    );
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Implement</h1>
          <p className="muted">
            Describe a change to this CRM. Hermes builds it in a sandbox, you try it in a preview,
            and it goes live when you approve.
          </p>
        </div>
      </header>

      <div className="implement">
        <div>
          {!unfinished && (
            <form className="panel form" onSubmit={open}>
              <label className="field">
                <span>What should change?</span>
                <textarea
                  rows={3}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="For example: add a 'lead source' field to contacts, with a filter for it."
                  required
                />
              </label>
              <div className="examples">
                {EXAMPLES.map((example) => (
                  <button key={example} type="button" className="chip" onClick={() => setText(example)}>
                    {example}
                  </button>
                ))}
              </div>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              <footer className="form-actions">
                <button type="submit" className="button primary">
                  Ask Hermes to build it
                </button>
              </footer>
            </form>
          )}
          {current && <RequestView key={current} id={current} onChanged={refresh} />}
        </div>

        <aside>
          <ReleasePanel refreshKey={refreshKey} />
          <section className="panel">
            <h2>History</h2>
            {list.length === 0 && <p className="muted">No changes requested yet.</p>}
            <ul className="history">
              {list.map((request) => (
                <li key={request.id}>
                  <button
                    type="button"
                    className={`history-item ${request.id === current ? "selected" : ""}`}
                    onClick={() => setSelected(request.id)}
                  >
                    <span>{request.title}</span>
                    <span className={`status status-${request.status}`}>
                      {STATUS_LABEL[request.status]}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </>
  );
}
