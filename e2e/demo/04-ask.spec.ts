// Video 4: ask about the data. The same question as an admin and as a sales user, who only
// gets their own numbers. Needs the local installation and an OpenRouter key.
//
//   BASE_URL=http://localhost:8100 npx playwright test --project=demo 04-ask

import { expect, test } from "@playwright/test";

import { ADMIN, openPage, SALES } from "../helpers";
import { caption, click, fastForward, installOverlay, saveVideo, screenshot, type } from "./support";

const QUESTION = "Which salesperson closed the most in the last quarter, and what was the average deal size?";

test("ask", async ({ page }) => {
  const answer = page.getByTestId("answer");
  await installOverlay(page);
  await page.goto("/");
  await type(page, page.getByLabel("E-mail"), ADMIN.email);
  await type(page, page.getByLabel("Password"), ADMIN.password);
  await click(page, page.getByRole("button", { name: "Sign in" }));

  await caption(page, "Ask a question about the data in plain language", 500);
  await openPage(page, "Ask");
  await type(page, page.getByLabel("Your question"), QUESTION);
  await click(page, page.getByRole("button", { name: "Ask", exact: true }), 500);
  await fastForward(page, "The analyst writes SQL and runs it read-only", () =>
    expect(answer).toBeVisible({ timeout: 3 * 60 * 1000 }), 3);
  await caption(page, "The answer, with the rows behind it", 3500);
  await click(page, page.getByText(/Show the SQL/), 600);
  await caption(page, "And the SQL that produced the numbers, so they can be checked", 3500);
  await screenshot(page, "screen-ask-admin");

  await caption(page, "Now the same question as a sales user", 600);
  await click(page, page.getByRole("button", { name: "Sign out" }));
  await type(page, page.getByLabel("E-mail"), SALES.email);
  await type(page, page.getByLabel("Password"), SALES.password);
  await click(page, page.getByRole("button", { name: "Sign in" }));
  await openPage(page, "Ask");
  await type(page, page.getByLabel("Your question"), QUESTION);
  await click(page, page.getByRole("button", { name: "Ask", exact: true }), 500);
  await fastForward(page, "Same agent, same tools: the database filters the rows", () =>
    expect(answer).toBeVisible({ timeout: 3 * 60 * 1000 }), 3);
  await caption(page, "Priya only gets her own deals: enforced by row-level security", 4000);
  await click(page, page.getByText(/Show the SQL/), 600);
  await caption(page, "The query is the same kind; PostgreSQL decides what it may return", 3500);
  await screenshot(page, "screen-ask-sales");

  await saveVideo(page, "04-ask");
});
