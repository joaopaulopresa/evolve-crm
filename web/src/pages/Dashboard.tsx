import { Link } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { day, money } from "../format";
import { type Dashboard, stageLabel } from "../types";
import { useLoad } from "../useLoad";

export function DashboardPage() {
  const { user } = useAuth();
  const { data, error, reload } = useLoad(() => api<Dashboard>("/dashboard"), []);

  async function complete(taskId: number) {
    await api(`/activities/${taskId}`, { method: "PATCH", body: { completed: true } });
    reload();
  }

  if (error) return <p className="form-error">{error}</p>;
  if (!data) return null;

  const openValue = data.pipeline.reduce((sum, row) => sum + row.value, 0);
  const openCount = data.pipeline.reduce((sum, row) => sum + row.count, 0);

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="muted">
            {user!.role === "admin" ? "Everyone's deals and tasks." : "Your deals and tasks."}
          </p>
        </div>
      </header>

      <section className="figures" aria-label="Summary">
        <div>
          <span className="figure" data-testid="open-pipeline">
            {money(openValue)}
          </span>
          <span className="muted">open pipeline across {openCount} deals</span>
        </div>
        <div>
          <span className="figure" data-testid="won-this-month">
            {money(data.won_this_month.value)}
          </span>
          <span className="muted">won this month in {data.won_this_month.count} deals</span>
        </div>
        <div>
          <span className={`figure ${data.overdue_tasks.length ? "warn" : ""}`}>
            {data.overdue_tasks.length}
          </span>
          <span className="muted">overdue tasks</span>
        </div>
      </section>

      <section className="panel">
        <h2>Pipeline value by stage</h2>
        <ul className="stage-bars">
          {data.pipeline.map((row) => (
            <li key={row.stage}>
              <span className="stage-name">{stageLabel(row.stage)}</span>
              <span className="stage-track">
                <span
                  className={`stage-fill stage-${row.stage}`}
                  style={{ width: `${openValue ? (row.value / openValue) * 100 : 0}%` }}
                />
              </span>
              <span className="stage-value">{money(row.value)}</span>
              <span className="muted stage-count">{row.count} deals</span>
            </li>
          ))}
        </ul>
        <Link to="/pipeline" className="text-link">
          Open the pipeline board
        </Link>
      </section>

      <section className="panel">
        <h2>Overdue tasks</h2>
        {data.overdue_tasks.length === 0 ? (
          <p className="muted">Nothing overdue.</p>
        ) : (
          <ul className="task-list">
            {data.overdue_tasks.map((task) => (
              <li key={task.id}>
                <input
                  type="checkbox"
                  aria-label={`Complete ${task.subject}`}
                  onChange={() => complete(task.id)}
                />
                <span>{task.subject}</span>
                <span className="muted">{task.owner_name}</span>
                <span className="warn">due {day(task.due_date)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
