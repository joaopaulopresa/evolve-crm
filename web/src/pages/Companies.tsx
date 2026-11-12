import { type FormEvent, useState } from "react";

import { api } from "../api";
import { TextField } from "../components/Field";
import { Modal } from "../components/Modal";
import type { Company } from "../types";
import { useLoad } from "../useLoad";

function CompanyDialog(props: { company: Company | null; onClose: () => void; onSaved: () => void }) {
  const { company, onClose, onSaved } = props;
  const [form, setForm] = useState({
    name: company?.name ?? "",
    industry: company?.industry ?? "",
    website: company?.website ?? "",
    city: company?.city ?? "",
    country: company?.country ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const set = (field: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm({ ...form, [field]: event.target.value });

  async function save(event: FormEvent) {
    event.preventDefault();
    const body = Object.fromEntries(
      Object.entries(form).map(([key, value]) => [key, value || (key === "name" ? "" : null)]),
    );
    try {
      if (company) await api(`/companies/${company.id}`, { method: "PATCH", body });
      else await api("/companies", { method: "POST", body });
      onSaved();
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  return (
    <Modal title={company ? "Edit company" : "New company"} onClose={onClose}>
      <form className="form" onSubmit={save}>
        <TextField label="Name" value={form.name} onChange={set("name")} required />
        <div className="form-row">
          <TextField label="Industry" value={form.industry} onChange={set("industry")} />
          <TextField label="Website" value={form.website} onChange={set("website")} />
        </div>
        <div className="form-row">
          <TextField label="City" value={form.city} onChange={set("city")} />
          <TextField label="Country" value={form.country} onChange={set("country")} />
        </div>
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
            {company ? "Save company" : "Create company"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

export function Companies() {
  const [search, setSearch] = useState("");
  const [industry, setIndustry] = useState("");
  const [editing, setEditing] = useState<Company | "new" | null>(null);
  const all = useLoad(() => api<Company[]>("/companies"), []);
  const companies = useLoad(
    () => api<Company[]>("/companies", { params: { q: search, industry } }),
    [search, industry],
  );
  const industries = [...new Set((all.data ?? []).map((c) => c.industry).filter(Boolean))].sort();

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Companies</h1>
          <p className="muted">{companies.data ? `${companies.data.length} companies` : " "}</p>
        </div>
        <button type="button" className="button primary" onClick={() => setEditing("new")}>
          New company
        </button>
      </header>

      <div className="filters">
        <input
          type="search"
          placeholder="Search by name"
          aria-label="Search companies"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select
          aria-label="Filter by industry"
          value={industry}
          onChange={(event) => setIndustry(event.target.value)}
        >
          <option value="">All industries</option>
          {industries.map((name) => (
            <option key={name} value={name!}>
              {name}
            </option>
          ))}
        </select>
      </div>

      {companies.error && <p className="form-error">{companies.error}</p>}
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Industry</th>
            <th>City</th>
            <th>Country</th>
            <th>Website</th>
          </tr>
        </thead>
        <tbody>
          {(companies.data ?? []).map((company) => (
            <tr key={company.id}>
              <td>
                <button type="button" className="row-link" onClick={() => setEditing(company)}>
                  {company.name}
                </button>
              </td>
              <td>{company.industry}</td>
              <td>{company.city}</td>
              <td>{company.country}</td>
              <td>{company.website}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {companies.data?.length === 0 && (
        <p className="empty">No companies match. Clear the search or add a new company.</p>
      )}

      {editing && (
        <CompanyDialog
          company={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            companies.reload();
            all.reload();
          }}
        />
      )}
    </>
  );
}
