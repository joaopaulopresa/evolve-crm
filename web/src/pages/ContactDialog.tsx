import { type FormEvent, useState } from "react";

import { api } from "../api";
import { SelectField, TextField } from "../components/Field";
import { Modal } from "../components/Modal";
import type { Company, Contact } from "../types";

type Props = {
  contact: Contact | null; // null creates a new contact
  companies: Company[];
  onClose: () => void;
  onSaved: () => void;
};

export function ContactDialog({ contact, companies, onClose, onSaved }: Props) {
  const [form, setForm] = useState({
    first_name: contact?.first_name ?? "",
    last_name: contact?.last_name ?? "",
    email: contact?.email ?? "",
    phone: contact?.phone ?? "",
    job_title: contact?.job_title ?? "",
    company_id: String(contact?.company_id ?? ""),
  });
  const [error, setError] = useState<string | null>(null);
  const set = (field: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm({ ...form, [field]: event.target.value });

  async function save(event: FormEvent) {
    event.preventDefault();
    const body = {
      ...form,
      email: form.email || null,
      phone: form.phone || null,
      job_title: form.job_title || null,
      company_id: form.company_id ? Number(form.company_id) : null,
    };
    try {
      if (contact) await api(`/contacts/${contact.id}`, { method: "PATCH", body });
      else await api("/contacts", { method: "POST", body });
      onSaved();
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  return (
    <Modal title={contact ? "Edit contact" : "New contact"} onClose={onClose}>
      <form className="form" onSubmit={save}>
        <div className="form-row">
          <TextField label="First name" value={form.first_name} onChange={set("first_name")} required />
          <TextField label="Last name" value={form.last_name} onChange={set("last_name")} required />
        </div>
        <TextField label="E-mail" type="email" value={form.email} onChange={set("email")} />
        <div className="form-row">
          <TextField label="Phone" value={form.phone} onChange={set("phone")} />
          <TextField label="Job title" value={form.job_title} onChange={set("job_title")} />
        </div>
        <SelectField label="Company" value={form.company_id} onChange={set("company_id")}>
          <option value="">No company</option>
          {companies.map((company) => (
            <option key={company.id} value={company.id}>
              {company.name}
            </option>
          ))}
        </SelectField>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <footer className="form-actions">
          <button type="button" className="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="button primary">
            {contact ? "Save contact" : "Create contact"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
