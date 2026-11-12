// Shapes returned by the API. Keep in sync with api/app/schemas.py.

export type Role = "admin" | "user";
export type Stage = "lead" | "qualified" | "proposal" | "negotiation" | "won" | "lost";
export type ActivityType = "note" | "call" | "meeting" | "task";

export const STAGES: { id: Stage; label: string }[] = [
  { id: "lead", label: "Lead" },
  { id: "qualified", label: "Qualified" },
  { id: "proposal", label: "Proposal" },
  { id: "negotiation", label: "Negotiation" },
  { id: "won", label: "Won" },
  { id: "lost", label: "Lost" },
];
export const OPEN_STAGES: Stage[] = ["lead", "qualified", "proposal", "negotiation"];
export const stageLabel = (stage: Stage) => STAGES.find((s) => s.id === stage)?.label ?? stage;

export type User = { id: number; email: string; name: string; role: Role };

export type Company = {
  id: number;
  name: string;
  industry: string | null;
  website: string | null;
  city: string | null;
  country: string | null;
};

export type Contact = {
  id: number;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  job_title: string | null;
  company_id: number | null;
  company_name: string | null;
};

export type Deal = {
  id: number;
  title: string;
  value: number;
  stage: Stage;
  company_id: number | null;
  company_name: string | null;
  contact_id: number | null;
  contact_name: string | null;
  owner_id: number;
  owner_name: string;
  expected_close_date: string | null;
  closed_at: string | null;
};

export type Activity = {
  id: number;
  type: ActivityType;
  subject: string;
  body: string | null;
  contact_id: number | null;
  deal_id: number | null;
  owner_id: number;
  owner_name: string;
  occurred_at: string;
  due_date: string | null;
  completed_at: string | null;
};

export type Dashboard = {
  pipeline: { stage: Stage; count: number; value: number }[];
  won_this_month: { count: number; value: number };
  overdue_tasks: Activity[];
};
