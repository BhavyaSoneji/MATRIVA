import { expect, test } from "@playwright/test";

// Minimal smoke test wiring Playwright into CI (issue #22). Frontend is still
// a Phase 0 scaffold with no interactive flows yet -- expand this with real
// feature tests (onboarding, chat, ANC visit card, etc.) as they land.
test("home page loads and shows the app name", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "MATRIVA" })).toBeVisible();
});
