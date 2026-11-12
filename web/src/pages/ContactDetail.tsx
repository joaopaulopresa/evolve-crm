import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import { SelectField, TextAreaField, TextField } from "../components/Field";
import { day, fullName } from "../format";
import type { Activity, ActivityType, Company, Contact } from "../types";
import { useLoad } from "../useLoad";
import { ContactDialog } from "./ContactDialog";

const TYPE_LABEL: Record<ActivityType, string> = {
  note: "Note",
  call: "Call",
  meeting: "Meeting",
  task: "Task",
};

export function ContactDetail() {
  const contactId = Number(useParams().contactId);
  const contact = useLoad(() => api<Contact>(`/contacts/${contactId}`), [contactId]);
  const companies = useLoad(() => api<Company[]>("/companies"), []);
  const activities = useLoad(
    () => api<Activity[]>("/activities", { params: { contact_id: contactId } }),
    [contactId],
  );
  const [editing, setEditing] = useState(false);
  const [type, setType] = useState<ActivityType>("note");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [dueDate, setDueDate] = useState("");

  async function addActivity(event: FormEvent) {
    event.preventDefault();
    await api("/activities", {
      method: "POST",
      body: {
        type,
        subject,
        body: body || null,
        contact_id: contactId,
        due_date: type === "task" && dueDate ? dueDate : null,
      },
    });
    setSubject("");
    setBody("");
    setDueDate("");
    activities.reload();
  }

  async function toggle(task: Activity) {
    await api(`/activities/${task.id}`, { method: "PATCH", body: { completed: !task.completed_at } });
    activities.reload();
  }

  if (contact.error) return <p className="form-error">{contact.error}</p>;
  if (!contact.data) return null;
  const person = contact.data;

  return (
    <>
      <header className="page-header">
        <div>
          <Link to="/contacts" className="text-link">
            All contacts
          </Link>
          <h1>{fullName(person)}</h1>
          <p className="muted">
            {[person.job_title, person.company_name].filter(Boolean).join(" at ")}
          </p>
        </div>
        <button type="button" className="button" onClick={() => setEditing(true)}>
          Edit contact
        </button>
      </header>

      <div className="detail">
        <section className="panel">
          <h2>Details</h2>
          <dl className="facts">
            <dt>E-mail</dt>
            <dd>{person.email ?? "Not set"}</dd>
            <dt>Phone</dt>
            <dd>{person.phone ?? "Not set"}</dd>
            <dt>Company</dt>
            <dd>{person.company_name ?? "Not set"}</dd>
          </dl>
        </section>

        <section className="panel">
          <h2>Timeline</h2>
          <form className="form activity-form" onSubmit={addActivity}>
            <div className="form-row">
              <SelectField
                label="Type"
                value={type}
                onChange={(e) => setType(e.target.value as ActivityType)}
              >
                {Object.entries(TYPE_LABEL).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </SelectField>
              <TextField
                label="Subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
              />
              {type === "task" && (
                <TextField
                  label="Due date"
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                />
              )}
            </div>
            <TextAreaField label="Details" value={body} onChange={(e) => setBody(e.target.value)} />
            <footer className="form-actions">
              <button type="submit" className="button primary">
                Add to timeline
              </button>
            </footer>
          </form>

          <ol className="timeline">
            {(activities.data ?? []).map((activity) => (
              <li key={activity.id} className={`timeline-item type-${activity.type}`}>
                <span className="timeline-type">{TYPE_LABEL[activity.type]}</span>
                <div>
                  <strong className={activity.completed_at ? "done" : ""}>{activity.subject}</strong>
                  {activity.body && <p>{activity.body}</p>}
                  <span className="muted">
                    {day(activity.occurred_at)} by {activity.owner_name}
                    {activity.due_date && `, due ${day(activity.due_date)}`}
                  </span>
                </div>
                {activity.type === "task" && (
                  <button type="button" className="link-button" onClick={() => toggle(activity)}>
                    {activity.completed_at ? "Reopen" : "Complete"}
                  </button>
                )}
              </li>
            ))}
          </ol>
          {activities.data?.length === 0 && (
            <p className="empty">Nothing here yet. Log the first note, call or task above.</p>
          )}
        </section>
      </div>

      {editing && (
        <ContactDialog
          contact={person}
          companies={companies.data ?? []}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            contact.reload();
          }}
        />
      )}
    </>
  );
}
