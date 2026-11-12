// Video 3: roll production back to the previous release. The lead source field (added in
// video 2) disappears and the data stays. Run after 02-change-request.
//
//   BASE_URL=http://localhost:8100 npx playwright test --project=demo 03-rollback

import { expect, test } from "@playwright/test";

import { ADMIN, openPage } from "../helpers";
import { caption, click, fastForward, installOverlay, saveVideo, screenshot, type } from "./support";

test("rollback", async ({ page }) => {
  await installOverlay(page);
  await page.goto("/");
  await type(page, page.getByLabel("E-mail"), ADMIN.email);
  await type(page, page.getByLabel("Password"), ADMIN.password);
  await click(page, page.getByRole("button", { name: "Sign in" }));

  await openPage(page, "Contacts");
  await expect(page.locator("main")).toContainText(/lead source/i);
  const people = await page.getByText(/^\d+ people$/).innerText();
  await caption(page, `Production has the lead source field, and ${people}`, 3000);

  await openPage(page, "Implement");
  const release = page.getByTestId("current-release");
  await expect(release).not.toHaveText("none");
  const before = await release.innerText();
  await caption(page, "One click rolls production back to the previous release", 1500);
  page.once("dialog", (dialog) => dialog.accept());
  await click(page, page.getByRole("button", { name: /Roll back to/ }), 800);
  await fastForward(
    page,
    "The deployer backs up, then redeploys the previous release",
    () => expect(release).not.toHaveText(before, { timeout: 5 * 60 * 1000 }),
    5,
  );
  await caption(page, "Production is on the previous release again", 2500);
  await screenshot(page, "screen-implement-rolled-back");

  await openPage(page, "Contacts");
  await expect(page.getByText(people)).toBeVisible({ timeout: 60000 });
  await expect(page.locator("main")).not.toContainText(/lead source/i, { timeout: 30000 });
  await caption(page, `The field is gone. The data is intact: still ${people}`, 3500);
  await caption(page, "The new column stays in the database, so the change can be restored", 3000);

  await saveVideo(page, "03-rollback");
});
