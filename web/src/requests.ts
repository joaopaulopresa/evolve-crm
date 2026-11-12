// How a change request is presented: status wording, and its events grouped for the timeline.

import type { RequestEvent, RequestStatus } from "./types";

export const STATUS_LABEL: Record<RequestStatus, string> = {
  open: "Waiting for a branch",
  queued: "Waiting for Hermes",
  working: "Hermes is working",
  needs_input: "Needs your reply",
  checking: "Running checks",
  checks_failed: "Checks failed",
  preview_ready: "Ready to try",
  approved: "Approved",
  deploying: "Deploying",
  live: "Live",
  deploy_failed: "Deploy failed",
  rolled_back: "Rolled back",
  discarded: "Discarded",
};

export const FINAL: RequestStatus[] = ["live", "deploy_failed", "rolled_back", "discarded"];
export const isFinal = (status: RequestStatus) => FINAL.includes(status);
/** Something is happening without the owner: keep refreshing. */
export const isBusy = (status: RequestStatus) =>
  ["queued", "working", "checking", "approved", "deploying"].includes(status);
export const canReply = (status: RequestStatus) =>
  ["needs_input", "checks_failed", "preview_ready"].includes(status);

export type TimelineItem =
  | { type: "event"; event: RequestEvent }
  | { type: "steps"; id: number; steps: RequestEvent[] };

/** Consecutive agent steps become one collapsible block; everything else stays as it is. */
export function buildTimeline(events: RequestEvent[]): TimelineItem[] {
  const items: TimelineItem[] = [];
  for (const event of events) {
    if (event.kind === "agent_started") continue;
    const last = items[items.length - 1];
    if (event.kind === "agent_step") {
      if (last?.type === "steps") last.steps.push(event);
      else items.push({ type: "steps", id: event.id, steps: [event] });
    } else {
      items.push({ type: "event", event });
    }
  }
  return items;
}

export const shortSha = (sha: string | null | undefined) => (sha ? sha.slice(0, 8) : "");
