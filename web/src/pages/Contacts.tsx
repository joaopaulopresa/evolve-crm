import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { fullName } from "../format";
import type { Company, Contact } from "../types";
import { useLoad } from "../useLoad";
import { ContactDialog } from "./ContactDialog";

export function Contacts() {
  const [search, setSearch] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [creating, setCreating] = useState(false);
  const companies = useLoad(() => api<Company[]>("/companies"), []);
  const contacts = useLoad(
    () => api<Contact[]>("/contacts", { params: { q: search, company_id: companyId } }),
    [search, companyId],
  );

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Contacts</h1>
          <p className="muted">{contacts.data ? `${contacts.data.length} people` : " "}</p>
        </div>
        <button type="button" className="button primary" onClick={() => setCreating(true)}>
          New contact
        </button>
      </header>

      <div className="filters">
        <input
          type="search"
          placeholder="Search by name, e-mail or company"
          aria-label="Search contacts"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select
          aria-label="Filter by company"
          value={companyId}
          onChange={(event) => setCompanyId(event.target.value)}
        >
          <option value="">All companies</option>
          {(companies.data ?? []).map((company) => (
            <option key={company.id} value={company.id}>
              {company.name}
            </option>
          ))}
        </select>
      </div>

      {contacts.error && <p className="form-error">{contacts.error}</p>}
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Company</th>
            <th>Job title</th>
            <th>E-mail</th>
            <th>Phone</th>
          </tr>
        </thead>
        <tbody>
          {(contacts.data ?? []).map((contact) => (
            <tr key={contact.id}>
              <td>
                <Link to={`/contacts/${contact.id}`} className="row-link">
                  {fullName(contact)}
                </Link>
              </td>
              <td>{contact.company_name}</td>
              <td>{contact.job_title}</td>
              <td>{contact.email}</td>
              <td>{contact.phone}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {contacts.data?.length === 0 && (
        <p className="empty">No contacts match. Clear the search or add a new contact.</p>
      )}

      {creating && (
        <ContactDialog
          contact={null}
          companies={companies.data ?? []}
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            contacts.reload();
          }}
        />
      )}
    </>
  );
}
