import { expect, test } from "vitest";

import { buildTimeline, canReply, isBusy, isFinal } from "./requests";
import type { RequestEvent } from "./types";

const event = (id: number, kind: string, message = ""): RequestEvent => ({
  id,
  kind,
  actor: "hermes",
  message,
  log: null,
  data: null,
  created_at: "2026-11-12T10:00:00Z",
});

test("agent steps are grouped between the other events", () => {
  const timeline = buildTimeline([
    event(1, "opened"),
    event(2, "agent_started"),
    event(3, "agent_step", "Ran: evolve-start 1"),
    event(4, "agent_step", "Edited api/app/models.py"),
    event(5, "agent_reply"),
    event(6, "checks_started"),
    event(7, "agent_step", "Ran: evolve-test"),
  ]);

  expect(timeline.map((item) => (item.type === "steps" ? item.steps.length : item.event.kind))).toEqual([
    "opened",
    2,
    "agent_reply",
    "checks_started",
    1,
  ]);
});

test("status helpers", () => {
  expect(isBusy("working")).toBe(true);
  expect(isBusy("preview_ready")).toBe(false);
  expect(canReply("preview_ready")).toBe(true);
  expect(canReply("deploying")).toBe(false);
  expect(isFinal("rolled_back")).toBe(true);
});
