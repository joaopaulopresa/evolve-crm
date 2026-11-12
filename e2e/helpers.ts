import { expect, type Page } from "@playwright/test";

export const ADMIN = { email: "admin@evolve.test", password: "admin123" };
export const SALES = { email: "priya@evolve.test", password: "demo1234" };

export async function signIn(page: Page, account = ADMIN) {
  await page.goto("/");
  await page.getByLabel("E-mail").fill(account.email);
  await page.getByLabel("Password").fill(account.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

/** Opens a page from the navigation rail. */
export async function openPage(page: Page, name: string) {
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name, exact: true }).click();
}
