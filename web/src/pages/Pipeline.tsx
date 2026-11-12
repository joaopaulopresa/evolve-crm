import { type DragEvent, useState } from "react";

import { api } from "../api";
import { day, initials, money } from "../format";
import { buildColumns } from "../pipeline";
import type { Company, Deal, Stage, User } from "../types";
import { useLoad } from "../useLoad";
import { DealDialog } from "./DealDialog";

export function Pipeline() {
  const deals = useLoad(() => api<Deal[]>("/deals"), []);
  const companies = useLoad(() => api<Company[]>("/companies"), []);
  const users = useLoad(() => api<User[]>("/users"), []);
  const [editing, setEditing] = useState<Deal | "new" | null>(null);
  const [dragOver, setDragOver] = useState<Stage | null>(null);

  async function move(dealId: number, stage: Stage) {
    await api(`/deals/${dealId}`, { method: "PATCH", body: { stage } });
    deals.reload();
  }

  function drop(event: DragEvent, stage: Stage) {
    event.preventDefault();
    setDragOver(null);
    const dealId = Number(event.dataTransfer.getData("text/plain"));
    if (dealId) void move(dealId, stage);
  }

  const columns = buildColumns(deals.data ?? []);

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Pipeline</h1>
          <p className="muted">Drag a deal to another stage, or open it to edit.</p>
        </div>
        <button type="button" className="button primary" onClick={() => setEditing("new")}>
          New deal
        </button>
      </header>
      {deals.error && <p className="form-error">{deals.error}</p>}

      <div className="board">
        {columns.map((column) => (
          <section
            key={column.stage}
            className={`column ${dragOver === column.stage ? "drag-over" : ""}`}
            aria-label={column.label}
            data-stage={column.stage}
            onDragOver={(event) => {
              event.preventDefault();
              setDragOver(column.stage);
            }}
            onDragLeave={() => setDragOver(null)}
            onDrop={(event) => drop(event, column.stage)}
          >
            <header className="column-header">
              <h2>
                {column.label} <span className="muted">{column.deals.length}</span>
              </h2>
              <span className="column-value">{money(column.value)}</span>
              <span className="share-track" aria-hidden="true">
                <span
                  className={`share-fill stage-${column.stage}`}
                  style={{ width: `${column.share * 100}%` }}
                />
              </span>
            </header>
            <ul className="cards">
              {column.deals.map((deal) => (
                <li key={deal.id}>
                  <button
                    type="button"
                    className="deal-card"
                    draggable
                    onDragStart={(event) => event.dataTransfer.setData("text/plain", String(deal.id))}
                    onClick={() => setEditing(deal)}
                  >
                    <strong>{deal.title}</strong>
                    <span className="muted">{deal.company_name ?? "No company"}</span>
                    <span className="deal-meta">
                      <span className="deal-value">{money(deal.value)}</span>
                      {deal.expected_close_date && (
                        <span className="muted">{day(deal.expected_close_date)}</span>
                      )}
                      <span className="avatar small" title={deal.owner_name}>
                        {initials(deal.owner_name)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      {editing && (
        <DealDialog
          deal={editing === "new" ? null : editing}
          companies={companies.data ?? []}
          users={users.data ?? []}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            deals.reload();
          }}
        />
      )}
    </>
  );
}
