import { defineConfig } from "@playwright/test";

// The stack must already be running: docker compose up -d
const baseURL = process.env.BASE_URL ?? "http://localhost:8080";

export default defineConfig({
  outputDir: "test-results",
  reporter: "list",
  workers: 1,
  use: { baseURL, viewport: { width: 1440, height: 900 } },
  projects: [
    { name: "e2e", testDir: "tests" },
    {
      // Scripts that record the demo videos into e2e/videos/. Run with: npm run demo
      name: "demo",
      testDir: "demo",
      timeout: 30 * 60 * 1000,
      use: {
        video: { mode: "on", size: { width: 1440, height: 900 } },
        launchOptions: { slowMo: 60 },
      },
    },
  ],
});
