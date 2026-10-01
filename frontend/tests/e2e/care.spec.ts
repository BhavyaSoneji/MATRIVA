import { expect, test, type Page, type Route } from "@playwright/test";

// Care features against a mocked backend: readings with flags, and the meal log with nutrient gaps.

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
};
const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", headers: CORS, body: JSON.stringify(body) });

async function mock(page: Page, state: { readings: unknown[]; posted: unknown[] }) {
  await page.addInitScript(() => window.localStorage.setItem("matriva_token", "test-token"));
  await page.route(/\/(auth\/me|pregnancy|pregnancy\/next-visit|wellness\/daily|wellness\/summary|resources|chat\/history|recommendations|care\/readings|care\/meals|care\/reminders)(\?.*)?$/, async (route) => {
    const req = route.request();
    if (req.resourceType() === "document") return route.fallback();
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    const path = new URL(req.url()).pathname;
    if (path === "/auth/me") return json(route, { id: "u1", email: "a@example.com", full_name: "Asha Verma", role: "user", is_active: true, created_at: "2026-01-01T00:00:00Z" });
    if (path === "/pregnancy") return json(route, { current_week: 22, due_date: null, first_pregnancy: true, stage: "second_trimester", trimester: 2 });
    if (path === "/pregnancy/next-visit") return json(route, { next_visit_week: 26, current_week: 22, message: "Next", source_id: "s", evidence_level: "supported" });
    if (path.startsWith("/wellness/daily")) return json(route, { detail: "none" }, 404);
    if (path === "/wellness/summary") return json(route, { days: [] });
    if (path === "/resources") return json(route, { verified_on: "2026-10-01", topics: {}, resources: [] });
    if (path === "/recommendations") return json(route, []);
    if (path === "/chat/history") return json(route, { detail: "none" }, 404);
    if (path === "/care/reminders") return json(route, { reminders: [] });
    if (path === "/care/readings" && req.method() === "POST") {
      state.posted.push(JSON.parse(req.postData() ?? "{}"));
      state.readings = [{ id: "r1", kind: "hb", date: "2026-10-01", value: 9.8, systolic: null, diastolic: null, context: null, unit: "g/dL", source: "manual",
        flags: [{ level: "soon", message: "Haemoglobin below 11 g/dL suggests anaemia in pregnancy. Talk to your doctor.", source: "WHO", url: "https://www.who.int" }] }];
      return json(route, state.readings[0], 201);
    }
    if (path === "/care/readings") return json(route, { readings: state.readings, weight_gain: null });
    if (path === "/care/meals")
      return json(route, { date: "2026-10-01", meals: [{ id: "m1", meal_type: "lunch", text: "2 roti, dal", items: [{ id: "roti", name: "Roti", grams: 80 }], totals: {} }],
        totals: {}, rows: [{ nutrient: "iron", target: "27 mg", percent: 22 }], suggestions: [{ nutrient: "iron", foods: [{ name: "Spinach (palak)", serving_g: 100, amount: 2.7 }] }], note: "Approximate." });
    return route.fallback();
  });
}

test("readings: add a haemoglobin value and see the sourced flag", async ({ page }) => {
  const state = { readings: [] as unknown[], posted: [] as unknown[] };
  await mock(page, state);
  await page.goto("/chat");
  await page.getByPlaceholder(/Ask anything/).fill("/readings");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Health readings" })).toBeVisible();
  await page.getByLabel(/Haemoglobin \(g\/dL\)/).fill("9.8");
  await page.getByRole("button", { name: "Add today" }).click();
  await expect(page.getByText(/suggests anaemia/)).toBeVisible();
  await expect(page.getByRole("link", { name: "WHO" })).toBeVisible();
  expect(state.posted).toEqual([{ kind: "hb", value: 9.8 }]);
});

test("meals: today's log shows the iron gap and a food that fills it", async ({ page }) => {
  await mock(page, { readings: [], posted: [] });
  await page.goto("/chat");
  await page.getByPlaceholder(/Ask anything/).fill("/meals");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "What I ate today" })).toBeVisible();
  await expect(page.getByText(/22%/)).toBeVisible();
  await expect(page.getByText(/Spinach/)).toBeVisible();
});
