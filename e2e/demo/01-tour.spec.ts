// Video 1: a tour of the CRM (sign-in, dashboard, pipeline board, a contact's timeline).

import { expect, test } from "@playwright/test";

import { ADMIN, openPage } from "../helpers";
import { caption, click, drag, glideTo, installOverlay, saveVideo, screenshot, type } from "./support";

test("tour", async ({ page }) => {
  await installOverlay(page);
  await page.goto("/");
  await screenshot(page, "screen-sign-in");
  await caption(page, "Evolve CRM: companies, contacts, deals and activities");
  await type(page, page.getByLabel("E-mail"), ADMIN.email);
  await type(page, page.getByLabel("Password"), ADMIN.password);
  await click(page, page.getByRole("button", { name: "Sign in" }));

  await expect(page.getByTestId("open-pipeline")).toBeVisible();
  await caption(page, "The dashboard: open pipeline, wins this month, overdue tasks", 2600);
  await screenshot(page, "screen-dashboard");
  await glideTo(page, page.getByRole("heading", { name: "Overdue tasks" }));
  await caption(page, "Tick a task to complete it", 900);
  await click(page, page.getByRole("checkbox").first(), 1200);

  await caption(page, "The pipeline board groups deals by stage", 600);
  await click(page, page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Pipeline" }));
  await expect(page.locator(".deal-card").first()).toBeVisible();
  await page.waitForTimeout(1500);
  await screenshot(page, "screen-pipeline");

  await caption(page, "Drag a deal to move it to the next stage", 1200);
  const lead = page.getByRole("region", { name: "Lead" });
  const qualified = page.getByRole("region", { name: "Qualified" });
  const card = lead.locator(".deal-card").first();
  const title = await card.locator("strong").innerText();
  await drag(page, card, qualified.locator(".column-header"));
  await expect(qualified.getByText(title)).toBeVisible();
  await page.waitForTimeout(1200);

  await caption(page, "Open a deal to edit it", 800);
  await click(page, qualified.getByText(title), 1500);
  await click(page, page.getByRole("button", { name: "Cancel" }));
  // Put the deal back so the recording can be repeated.
  await drag(page, qualified.getByText(title), lead.locator(".column-header"));

  await caption(page, "Contacts, with search and a company filter", 600);
  await openPage(page, "Contacts");
  await type(page, page.getByLabel("Search contacts"), "nordhaven");
  await page.waitForTimeout(900);
  await screenshot(page, "screen-contacts");
  await click(page, page.getByRole("link", { name: "Sanne de Vries" }));

  await expect(page.getByRole("heading", { name: "Timeline" })).toBeVisible();
  await caption(page, "Each contact has a timeline of notes, calls, meetings and tasks", 2200);
  await type(page, page.getByLabel("Subject"), "Asked for a revised quote");
  await click(page, page.getByRole("button", { name: "Add to timeline" }), 1500);
  await screenshot(page, "screen-contact-timeline");
  await caption(page, "Everything here runs on fictional demo data", 2200);

  await saveVideo(page, "01-tour");
});
