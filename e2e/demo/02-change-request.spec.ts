// Video 2: the owner asks for a change, Hermes builds it, the owner tries the preview, asks for
// an adjustment, approves, and production has it. Ends on the Langfuse trace and the Grafana
// delivery dashboard. Needs the full local installation (deploy/install.sh), the observability
// stack and an OpenRouter key. Takes about fifteen minutes; the video is cut to about two.
//
//   BASE_URL=http://localhost:8100 npx playwright test --project=demo 02-change-request

import { expect, test } from "@playwright/test";

import { ADMIN, openPage } from "../helpers";
import { caption, click, fastForward, glideTo, heroClip, installOverlay, saveVideo, screenshot, type } from "./support";

const REQUEST = "Add a 'lead source' field to contacts, with a filter for it on the contacts page.";
const ADJUSTMENT =
  "Make lead source a dropdown with these options: Website, Referral, Event, Cold outreach, Social media, Partner.";
const LANGFUSE = process.env.LANGFUSE_URL ?? "http://localhost:3300";
const GRAFANA = process.env.GRAFANA_URL ?? "http://localhost:3301";
const SLOW = { timeout: 25 * 60 * 1000 };

test("change request", async ({ page, baseURL }) => {
  const status = page.getByTestId("request-status");
  await installOverlay(page);
  await page.goto("/");
  await type(page, page.getByLabel("E-mail"), ADMIN.email);
  await type(page, page.getByLabel("Password"), ADMIN.password);
  await click(page, page.getByRole("button", { name: "Sign in" }));

  await caption(page, "Contacts today: no way to record where a lead came from", 500);
  await openPage(page, "Contacts");
  await page.waitForTimeout(2200);

  await caption(page, "The owner describes the change in plain language", 500);
  await openPage(page, "Implement");
  await heroClip(4, async () => {
    await type(page, page.getByLabel("What should change?"), REQUEST);
    await click(page, page.getByRole("button", { name: "Ask Hermes to build it" }), 1500);
  });

  await heroClip(3, async () => {
    await fastForward(page, "Hermes implements it in a sandbox: code, migration and tests", () =>
      expect(status).toHaveText(/Running checks|Ready to try/, SLOW),
    );
  });
  await fastForward(page, "The pipeline checks the branch and builds a preview", () =>
    expect(status).toHaveText("Ready to try", SLOW),
  );
  await heroClip(2.5, async () => {
    await caption(page, "Hermes replies in plain language and the preview is ready", 2500);
  });
  await screenshot(page, "screen-implement-preview-ready");

  await caption(page, "The preview is a separate copy of the app, on demo data", 800);
  const previewUrl = (await page.getByRole("link", { name: /Open the preview/ }).getAttribute("href"))!;
  await glideTo(page, page.getByRole("link", { name: /Open the preview/ }));
  await page.goto(previewUrl);
  await type(page, page.getByLabel("E-mail"), ADMIN.email);
  await type(page, page.getByLabel("Password"), ADMIN.password);
  await click(page, page.getByRole("button", { name: "Sign in" }));
  await openPage(page, "Contacts");
  await expect(page.locator("main")).toContainText(/lead source/i);
  await caption(page, "In the preview: contacts now have a lead source and a filter", 3200);

  await caption(page, "Back in the CRM, the owner asks for one adjustment", 500);
  await page.goto(`${baseURL}/implement`);
  await type(page, page.getByLabel("Ask Hermes for an adjustment"), ADJUSTMENT);
  await click(page, page.getByRole("button", { name: "Send to Hermes" }), 1500);
  await fastForward(page, "Hermes continues on the same branch and the preview is rebuilt", async () => {
    await expect(status).not.toHaveText("Ready to try", SLOW);
    await expect(status).toHaveText("Ready to try", SLOW);
  });
  await caption(page, "The adjusted change is ready to try again", 2200);

  await caption(page, "Approve: merge, back up, deploy to production, smoke test", 600);
  await heroClip(3, async () => {
    await click(page, page.getByRole("button", { name: "Approve and deploy" }), 800);
    await fastForward(page, "Deploying to production", () => expect(status).toHaveText("Live", SLOW), 2);
    await page.waitForTimeout(1500);
  });
  await caption(page, "Live in production, with the tokens and cost of the request", 2500);
  await screenshot(page, "screen-implement-live");
  const traceUrl = await page.getByRole("link", { name: "Open the trace in Langfuse" }).getAttribute("href");

  await heroClip(3.5, async () => {
    await openPage(page, "Contacts");
    await expect(page.locator("main")).toContainText(/lead source/i, { timeout: 30000 });
    await caption(page, "Production now has the lead source field and filter", 3000);
  });
  await screenshot(page, "screen-contacts-lead-source");

  await caption(page, "Every model call of the request is traced in Langfuse", 400);
  await page.goto(`${LANGFUSE}/auth/sign-in`);
  await page.getByLabel(/email/i).fill("admin@evolve.test");
  await page.getByLabel(/password/i).fill(process.env.LANGFUSE_PASSWORD ?? "admin12345");
  await page.getByRole("button", { name: /sign in/i }).first().click();
  await page.waitForURL((url) => !url.pathname.includes("sign-in"), { timeout: 30000 });
  await page.goto(traceUrl ?? `${LANGFUSE}/project/evolve-crm/sessions`);
  await page.waitForTimeout(4000);
  await caption(page, "Langfuse: the session of this change request, prompts and tool calls", 4000);
  await screenshot(page, "screen-langfuse-trace");

  await page.goto(`${GRAFANA}/d/evolve-delivery/evolve-crm-delivery?kiosk&from=now-30m&to=now`);
  await page.waitForTimeout(5000);
  await caption(page, "Grafana: deploys, previews and change requests", 4000);
  await screenshot(page, "screen-grafana-delivery");

  await saveVideo(page, "02-change-request");
});
