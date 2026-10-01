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

// ---- what to eat -------------------------------------------------------------------------------------------------------

const GUIDE = {
  week: 21, month: 5, diet: "vegetarian",
  traditional: {
    book: { title: "Prasuti Tantra", author: "Prof. Premvati Tiwari", chapter: "5", section: "Month-wise dietary regimen", scan_pages: "135-142", note: "n" },
    evidence_level: "traditional", month: 5, months_available: [1, 2, 3, 4, 5, 6, 7, 8, 9],
    foods: [{ authority: "Harita", text: "Payasa (rice cooked with milk and sweetened).", page: 136, paraphrased: false }],
    medicated: [{ authority: "Caraka", text: "Ghrta medicated with the drugs of madhura group.", page: 136 }],
    procedures: [], skipped_for_diet: 1, skipped_for_allergy: 1,
    medicated_note: "The book also describes milk, ghee or rice prepared with named herbs, and enemas. MATRIVA does not advise on them.",
    rationale: { page: "139-140", points: ["Cold and sweet liquid diet prevents dehydration."] },
    avoid: { page: "141-142", items: [{ authority: "Harita", text: "Pulses, garlic and onion.", page: 142, modern: "Dal is recommended by ICMR-NIN." }] },
  },
  modern: {
    needs: [{ id: "iron", label: "Iron", reason: "low haemoglobin" }, { id: "calcium", label: "Calcium", reason: "bones" }],
    need: null, foods: [], allergy_notes: ["Left out because of your allergies: milk and dairy."],
  },
  avoid_modern: [{ name: "Raw eggs", why: "can carry salmonella", sources: [{ name: "NHS", url: "https://www.nhs.uk/" }] }],
  notes: ["Foods only. MATRIVA does not advise on medicines."],
};

test("what to eat: the book's month, the medicated preparations kept apart, and foods rich in a nutrient", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("matriva_token", "test-token"));
  const asked: string[] = [];
  await page.route(/\/(auth\/me|pregnancy|pregnancy\/next-visit|wellness\/daily|wellness\/summary|resources|chat\/history|recommendations|care\/food-guide|care\/reminders)(\?.*)?$/, async (route) => {
    const req = route.request();
    if (req.resourceType() === "document") return route.fallback();
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    const url = new URL(req.url());
    const path = url.pathname;
    if (path === "/auth/me") return json(route, { id: "u1", email: "a@example.com", full_name: "Asha Verma", role: "user", is_active: true, created_at: "2026-01-01T00:00:00Z" });
    if (path === "/pregnancy") return json(route, { current_week: 21, due_date: null, first_pregnancy: true, stage: "second_trimester", trimester: 2 });
    if (path === "/pregnancy/next-visit") return json(route, { next_visit_week: 26, current_week: 21, message: "Next", source_id: "s", evidence_level: "supported" });
    if (path.startsWith("/wellness/daily")) return json(route, { detail: "none" }, 404);
    if (path === "/wellness/summary") return json(route, { days: [] });
    if (path === "/resources") return json(route, { verified_on: "2026-10-01", topics: {}, resources: [] });
    if (path === "/recommendations") return json(route, []);
    if (path === "/chat/history") return json(route, { detail: "none" }, 404);
    if (path === "/care/reminders") return json(route, { reminders: [] });
    if (path === "/care/food-guide") {
      asked.push(url.search);
      const need = url.searchParams.get("need");
      return json(route, need === "iron"
        ? { ...GUIDE, modern: { ...GUIDE.modern, need: { id: "iron", label: "Iron", reason: "low haemoglobin", unit: "mg", daily_allowance: 27, tip: "Eat it with a vitamin C food." },
            foods: [{ name: "Lentils (masoor dal)", category: "legume", serving_g: 150, amount: 5, percent: 18 }], sources: [{ name: "USDA FoodData Central", url: "https://fdc.nal.usda.gov/" }] } }
        : GUIDE);
    }
    return route.fallback();
  });

  await page.goto("/chat");
  await page.getByRole("textbox").first().fill("/foods");
  await page.keyboard.press("Enter");
  await expect(page.getByText("From the book · traditional (Ayurveda)")).toBeVisible();
  await expect(page.getByText("Payasa (rice cooked with milk and sweetened).")).toBeVisible();
  await expect(page.getByText(/Harita · scanned p\. 136/)).toBeVisible();
  await expect(page.getByText(/1 more entry for this month use ingredients outside your diet/)).toBeVisible();
  await expect(page.getByText(/1 entry for this month contain something you are allergic to/)).toBeVisible();
  await expect(page.getByText("Left out because of your allergies: milk and dairy.")).toBeVisible();
  // the herb-medicated preparation is not shown as food: it sits in a collapsed "not advice" section
  await expect(page.getByText("Ghrta medicated with the drugs of madhura group.")).toBeHidden();
  await page.getByText(/Treatments the book also describes/).click();
  await expect(page.getByText("Ghrta medicated with the drugs of madhura group.")).toBeVisible();
  await expect(page.getByText(/MATRIVA does not advise on them/)).toBeVisible();

  await page.getByRole("button", { name: "Iron" }).click();
  await expect(page.getByText("Lentils (masoor dal)")).toBeVisible();
  await expect(page.getByText(/pregnancy allowance 27 mg a day/)).toBeVisible();
  await expect(page.getByText("Eat it with a vitamin C food.")).toBeVisible();
  expect(asked.some((q) => q.includes("need=iron"))).toBe(true);
});
