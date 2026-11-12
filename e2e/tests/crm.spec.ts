import { expect, test } from "@playwright/test";

import { openPage, SALES, signIn } from "../helpers";

test("the dashboard shows the seeded pipeline", async ({ page }) => {
  await signIn(page);

  await expect(page.getByTestId("open-pipeline")).toContainText("$");
  await expect(page.getByRole("heading", { name: "Overdue tasks" })).toBeVisible();
});

test("create a deal, move it to another stage, then delete it", async ({ page }) => {
  const title = `E2E deal ${Date.now()}`;
  await signIn(page);
  await openPage(page, "Pipeline");

  await page.getByRole("button", { name: "New deal" }).click();
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("Value (USD)").fill("4200");
  await page.getByRole("button", { name: "Create deal" }).click();

  const lead = page.getByRole("region", { name: "Lead" });
  const proposal = page.getByRole("region", { name: "Proposal" });
  await expect(lead.getByText(title)).toBeVisible();

  await lead.getByText(title).dragTo(proposal, { targetPosition: { x: 60, y: 40 } });
  await expect(proposal.getByText(title)).toBeVisible();
  await expect(lead.getByText(title)).toHaveCount(0);

  await proposal.getByText(title).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete deal" }).click();
  await expect(page.getByText(title)).toHaveCount(0);
});

test("search contacts and log a note on a contact's timeline", async ({ page }) => {
  const subject = `E2E note ${Date.now()}`;
  await signIn(page);
  await openPage(page, "Contacts");

  await page.getByLabel("Search contacts").fill("Sanne");
  await page.getByRole("link", { name: "Sanne de Vries" }).click();
  await expect(page.getByRole("heading", { name: "Sanne de Vries" })).toBeVisible();

  await page.getByLabel("Subject").fill(subject);
  await page.getByRole("button", { name: "Add to timeline" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: subject })).toBeVisible();
});

test("a sales user sees only their own deals", async ({ page }) => {
  await signIn(page, SALES);
  await openPage(page, "Pipeline");

  const owners = page.locator(".deal-card .avatar");
  await expect(owners.first()).toBeVisible();
  const titles = await owners.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("title")));
  expect(new Set(titles)).toEqual(new Set(["Priya Raman"]));
});
