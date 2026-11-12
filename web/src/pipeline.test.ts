import { expect, test } from "vitest";

import { buildColumns } from "./pipeline";
import type { Deal, Stage } from "./types";

const deal = (id: number, stage: Stage, value: number) => ({ id, stage, value }) as Deal;

test("groups deals by stage and totals each column", () => {
  const columns = buildColumns([deal(1, "lead", 1000), deal(2, "lead", 3000), deal(3, "won", 9000)]);

  expect(columns.map((column) => column.stage)).toEqual([
    "lead",
    "qualified",
    "proposal",
    "negotiation",
    "won",
    "lost",
  ]);
  expect(columns[0]).toMatchObject({ value: 4000, share: 1 });
  expect(columns[0]!.deals).toHaveLength(2);
});

test("share only counts open stages", () => {
  const columns = buildColumns([deal(1, "lead", 1000), deal(2, "proposal", 3000), deal(3, "won", 9000)]);
  const share = Object.fromEntries(columns.map((column) => [column.stage, column.share]));

  expect(share.lead).toBe(0.25);
  expect(share.proposal).toBe(0.75);
  expect(share.won).toBe(0);
});
