// The development stack is not connected to the factory: the pages must say so plainly.

import { expect, test } from "@playwright/test";

import { openPage, SALES, signIn } from "../helpers";

test("Implement explains that only production can change itself", async ({ page }) => {
  await signIn(page);
  await openPage(page, "Implement");

  await expect(page.getByText("cannot change itself")).toBeVisible();
});

test("Ask explains that the analyst is not connected", async ({ page }) => {
  await signIn(page);
  await openPage(page, "Ask");

  await expect(page.getByText("is not connected to the analyst")).toBeVisible();
});

test("sales users do not get the Implement page", async ({ page }) => {
  await signIn(page, SALES);

  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Ask" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Implement" })).toHaveCount(0);
  await page.goto("/implement");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});
