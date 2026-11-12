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

// --- Implement and Ask (see api/app/implementation) ---------------------------------------------

export type Features = {
  environment: string;
  implement: boolean;
  implement_agent: boolean;
  ask: boolean;
  ask_disabled_by_owner: boolean;
};

export type RequestStatus =
  | "open"
  | "queued"
  | "working"
  | "needs_input"
  | "checking"
  | "checks_failed"
  | "preview_ready"
  | "approved"
  | "deploying"
  | "live"
  | "deploy_failed"
  | "rolled_back"
  | "discarded";

export type RequestEvent = {
  id: number;
  kind: string;
  actor: string;
  message: string | null;
  log: string | null;
  data: Record<string, unknown> | null;
  created_at: string;
};

export type ChangeRequest = {
  id: number;
  title: string;
  description: string;
  status: RequestStatus;
  branch: string | null;
  head_sha: string | null;
  preview_url: string | null;
  summary: string | null;
  tokens: number;
  cost_usd: number | null;
  trace_url: string | null;
  requested_by_name: string;
  approved_by_name: string | null;
  created_at: string;
  updated_at: string;
  events?: RequestEvent[];
};

export type Releases = {
  current: string | null;
  rollback_target: string | null;
  busy: boolean;
  history: { sha: string; kind: string; ok: boolean; at: string; change_request_id?: number | null }[];
};

export type AskQuery = {
  sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  error: string | null;
};

export type AskAnswer = { answer: string; queries: AskQuery[]; conversation_id: string };
