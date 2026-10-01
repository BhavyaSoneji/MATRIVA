import { expect, test, type Page, type Route } from "@playwright/test";

// Safety guard rails against a mocked backend: the chat shows a caution and the rule behind it, and the Settings
// page saves the safety profile without erasing what it does not show.

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
};
const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", headers: CORS, body: JSON.stringify(body) });
const sse = (events: [string, unknown][]) =>
  events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");

const PROFILE = {
  user_id: "u1",
  consent: true,
  consent_version: "2026-01",
  full_name: "Asha Verma",
  health: {
    known_conditions: ["thyroid", "Migraine on and off"],
    doctor_restrictions: ["no heavy lifting"],
    dietary_restrictions: [],
    activity_restrictions: [],
    allergies: ["penicillin"],
    current_medications: ["Thyronorm 50 mcg"],
    risk_factors: ["rh_negative"],
    age_years: 36,
    blood_group: "O-",
    notes: "keep",
  },
  lifestyle: { activity_level: "light", occupation: "teacher", sleep_hours: 7, stress_level: null, preferences: [] },
  dietary: { diet_type: "vegetarian", region: "Gujarat", cuisine: "Gujarati", food_preferences: [], allergies: [] },
  cultural: { language: "gu", region: "Gujarat", traditional_practice_preference: "balanced", cultural_notes: null },
};

async function mock(page: Page, puts: { profile: Record<string, unknown>[] }) {
  await page.addInitScript(() => window.localStorage.setItem("matriva_token", "test-token"));
  await page.route(/\/(auth\/me|profile|pregnancy|pregnancy\/next-visit|wellness\/daily|wellness\/summary|resources|chat\/stream|chat\/history|recommendations|care\/[a-z-]+)(\?.*)?$/, async (route) => {
    const req = route.request();
    if (req.resourceType() === "document") return route.fallback();
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    const path = new URL(req.url()).pathname;
    if (path === "/auth/me") return json(route, { id: "u1", email: "a@example.com", full_name: "Asha Verma", role: "user", is_active: true, created_at: "2026-01-01T00:00:00Z" });
    if (path === "/profile" && req.method() === "PUT") {
      puts.profile.push(JSON.parse(req.postData() ?? "{}"));
      return json(route, PROFILE);
    }
    if (path === "/profile") return json(route, PROFILE);
    if (path === "/pregnancy" && req.method() === "PUT") return json(route, { current_week: 22, due_date: null, first_pregnancy: true, stage: "second_trimester", trimester: 2 });
    if (path === "/pregnancy") return json(route, { current_week: 22, due_date: null, first_pregnancy: true, stage: "second_trimester", trimester: 2 });
    if (path === "/pregnancy/next-visit") return json(route, { next_visit_week: 26, current_week: 22, message: "Next", source_id: "s", evidence_level: "supported" });
    if (path.startsWith("/wellness/daily")) return json(route, { detail: "none" }, 404);
    if (path === "/wellness/summary") return json(route, { days: [] });
    if (path === "/resources") return json(route, { verified_on: "2026-10-01", topics: {}, resources: [] });
    if (path === "/recommendations") return json(route, []);
    if (path === "/chat/history") return json(route, { detail: "none" }, 404);
    if (path === "/care/emergency-contact") return json(route, { contact: null });
    if (path === "/care/reminders") return json(route, { reminders: [] });
    if (path === "/chat/stream")
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: CORS,
        body: sse([
          ["delta", { text: "x" }],
          ["final", { answer: "⚠️ Caffeine: ACOG advises limiting caffeine to under 200 mg a day.\n\nI don't have enough reviewed information to answer this safely.", safety_status: "low_concern", citations: [], corrected: true }],
          ["done", { conversation_id: "c1", message_id: "m1", sources: [], suggestions: [], recommendations: [],
            evidence: { guardrails: [{ id: "sub-caffeine", kind: "substance", action: "caution", title: "Caffeine", matched: "coffee",
              sources: [{ key: "acog", name: "ACOG - Patient and clinical guidance", url: "https://www.acog.org/" }] }] } }],
        ]),
      });
    return route.fallback();
  });
}

test("a caution shows in front of the answer, with the rule and its source one click away", async ({ page }) => {
  await mock(page, { profile: [] });
  await page.goto("/chat");
  await page.getByRole("textbox").first().fill("Can I drink coffee?");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("note").filter({ hasText: "Caffeine: ACOG advises" })).toBeVisible();
  const why = page.getByText(/Why MATRIVA answered this way/);
  await expect(why).toBeVisible();
  await why.click();
  await expect(page.getByRole("link", { name: "ACOG - Patient and clinical guidance" })).toHaveAttribute("href", "https://www.acog.org/");
  await expect(page.getByText(/has not yet checked each rule/)).toBeVisible();
});

test("settings loads the safety profile and saves it without erasing the fields it does not show", async ({ page }) => {
  const puts: { profile: Record<string, unknown>[] } = { profile: [] };
  await mock(page, puts);
  await page.goto("/settings");

  await expect(page.getByLabel("Thyroid condition")).toBeChecked();
  await expect(page.getByLabel(/Anything else/)).toHaveValue("Migraine on and off");
  await expect(page.getByLabel(/Medicines, tablets/)).toHaveValue("Thyronorm 50 mcg");
  await expect(page.getByLabel("Your age")).toHaveValue("36");
  await expect(page.getByLabel("Blood group", { exact: true })).toHaveValue("O-");

  await page.getByLabel("High blood pressure").check();
  await page.getByLabel(/Medicines, tablets/).fill("Thyronorm 50 mcg\nEcosprin 75");
  await page.getByLabel("Expecting twins or more").check();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Your details were saved.")).toBeVisible();

  const sent = puts.profile[0];
  expect(sent.current_medications).toEqual(["Thyronorm 50 mcg", "Ecosprin 75"]);
  expect(sent.known_conditions).toEqual(expect.arrayContaining(["thyroid", "high blood pressure", "Migraine on and off"]));
  expect(sent.risk_factors).toEqual(expect.arrayContaining(["rh_negative", "twins"]));
  expect(sent.age_years).toBe(36);
  expect(sent.blood_group).toBe("O-");
  // untouched fields are sent back, not wiped
  expect(sent.language).toBe("gu");
  expect(sent.occupation).toBe("teacher");
  expect(sent.doctor_restrictions).toEqual(["no heavy lifting"]);
  expect(sent.allergies).toEqual(["penicillin"]);
});
