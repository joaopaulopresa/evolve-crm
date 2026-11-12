import { expect, test } from "vitest";

import { day, initials, money } from "./format";

test("money has no cents and a thousands separator", () => {
  expect(money(12500)).toBe("$12,500");
});

test("day keeps a date-only value on the same calendar day", () => {
  expect(day("2026-10-05")).toBe("Oct 5, 2026");
  expect(day(null)).toBe("");
});

test("initials use the first two words", () => {
  expect(initials("Maya Okafor Lind")).toBe("MO");
});
