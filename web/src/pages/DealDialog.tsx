import { type FormEvent, useState } from "react";

import { api } from "../api";
import { useAuth } from "../auth";
import { SelectField, TextField } from "../components/Field";
import { Modal } from "../components/Modal";
import { type Company, type Deal, type Stage, STAGES, type User } from "../types";

type Props = {
  deal: Deal | null; // null creates a new deal
  companies: Company[];
  users: User[];
  onClose: () => void;
  onSaved: () => void;
};

export function DealDialog({ deal, companies, users, onClose, onSaved }: Props) {
  const { user } = useAuth();
  const [title, setTitle] = useState(deal?.title ?? "");
  const [value, setValue] = useState(String(deal?.value ?? ""));
  const [stage, setStage] = useState<Stage>(deal?.stage ?? "lead");
  const [companyId, setCompanyId] = useState(String(deal?.company_id ?? ""));
  const [ownerId, setOwnerId] = useState(String(deal?.owner_id ?? user!.id));
  const [closeDate, setCloseDate] = useState(deal?.expected_close_date ?? "");
  const [error, setError] = useState<string | null>(null);

  async function save(event: FormEvent) {
    event.preventDefault();
    const body = {
      title,
      value: Number(value || 0),
      stage,
      company_id: companyId ? Number(companyId) : null,
      expected_close_date: closeDate || null,
      ...(user!.role === "admin" ? { owner_id: Number(ownerId) } : {}),
    };
    try {
      if (deal) await api(`/deals/${deal.id}`, { method: "PATCH", body });
      else await api("/deals", { method: "POST", body });
      onSaved();
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  async function remove() {
    if (!deal || !window.confirm(`Delete "${deal.title}"?`)) return;
    await api(`/deals/${deal.id}`, { method: "DELETE" });
    onSaved();
  }

  return (
    <Modal title={deal ? "Edit deal" : "New deal"} onClose={onClose}>
      <form className="form" onSubmit={save}>
        <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <div className="form-row">
          <TextField
            label="Value (USD)"
            type="number"
            min="0"
            step="1"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <SelectField label="Stage" value={stage} onChange={(e) => setStage(e.target.value as Stage)}>
            {STAGES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </SelectField>
        </div>
        <SelectField label="Company" value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
          <option value="">No company</option>
          {companies.map((company) => (
            <option key={company.id} value={company.id}>
              {company.name}
            </option>
          ))}
        </SelectField>
        <div className="form-row">
          <TextField
            label="Expected close"
            type="date"
            value={closeDate}
            onChange={(e) => setCloseDate(e.target.value)}
          />
          {user!.role === "admin" && (
            <SelectField label="Owner" value={ownerId} onChange={(e) => setOwnerId(e.target.value)}>
              {users.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </SelectField>
          )}
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <footer className="form-actions">
          {deal && (
            <button type="button" className="button danger" onClick={remove}>
              Delete deal
            </button>
          )}
          <button type="button" className="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="button primary">
            {deal ? "Save deal" : "Create deal"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
