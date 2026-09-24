import { expect, test } from "@playwright/test";

// Minimal smoke test wiring Playwright into CI (issue #22).
test("home page loads and shows the app name and headline", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "MATRIVA" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Calm, evidence-based guidance for every stage of your pregnancy" })
  ).toBeVisible();
});
