import { expect, test, type Page, type Route } from "@playwright/test";

// The backend is fully mocked, so these run in CI without an API: they check that the single
// chat workspace actually delivers everything that used to be separate pages.

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
};

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", headers: CORS, body: JSON.stringify(body) });

const VIDEO = {
  id: "yt-test",
  type: "video",
  topic: "nutrition",
  stages: ["all"],
  language: "en",
  title: "Eating well in the second trimester",
  publisher: "Test Channel",
  url: "https://www.youtube.com/watch?v=test",
  thumbnail: null,
  about: "A short explainer.",
};

const sse = (events: [string, unknown][]) =>
  events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");

async function mockBackend(page: Page, opts: { onChatBody?: (body: Record<string, unknown>) => void } = {}) {
  await page.addInitScript(() => window.localStorage.setItem("matriva_token", "test-token"));
  await page.route(/\/(auth\/me|pregnancy|pregnancy\/next-visit|wellness\/daily|wellness\/summary|resources|chat\/stream|chat\/history|recommendations|knowledge\/book|knowledge\/book\/glossary)(\?.*)?$/, async (route) => {
    const req = route.request();
    if (req.resourceType() === "document") return route.fallback(); // page navigations (e.g. /recommendations) are real
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    const path = new URL(req.url()).pathname;
    if (path === "/auth/me")
      return json(route, { id: "u1", email: "asha@example.com", full_name: "Asha Verma", role: "user", is_active: true, created_at: "2026-01-01T00:00:00Z" });
    if (path === "/pregnancy")
      return json(route, { current_week: 22, due_date: null, first_pregnancy: true, stage: "second_trimester", trimester: 2 });
    if (path === "/pregnancy/next-visit")
      return json(route, { next_visit_week: 26, current_week: 22, message: "Next antenatal contact", source_id: "s", evidence_level: "supported" });
    if (path.startsWith("/wellness/daily")) return json(route, { detail: "none" }, 404);
    if (path === "/wellness/summary") return json(route, { days: [] });
    if (path === "/resources") return json(route, { verified_on: "2026-10-01", topics: { nutrition: "Nutrition" }, resources: [VIDEO] });
    if (path === "/recommendations") return json(route, []);
    if (path === "/chat/history") return json(route, { detail: "none" }, 404);
    if (path === "/knowledge/book/glossary") return json(route, { query: "stanya", results: [{ hi: "स्तन्य", en: "Stanya or breast milk", count: 1, source: "contents" }] });
    if (path === "/knowledge/book")
      return json(route, {
        available: true, title: "Prasutitantra", author: "Prof. Premvati Tiwari", publisher: "Chaukhambha", source: "scan",
        authorities: { Vagbhata: 222, Caraka: 141 }, stats: { verified_sections: 93, english_chunks: 567, scanned_pages: 408 },
        review: { "1": "approved" },
        chapters: [{ number: 1, title_en: "Anatomy Of Female Reproductive System", title_hi: "स्त्री-शरीर-रचना", scan_start: 27, scan_end: 41,
          english_chunks: 17, english_words: 2000, sections: [{ title_en: "Pelvis", title_hi: "श्रोणि", printed_page: 3, scan_page: 28 }],
          concepts: [{ id: "garbha", label: "Garbha", count: 4 }], authorities: { Caraka: 3 }, key_terms: ["pesi"] }],
      });
    if (path === "/chat/stream") {
      opts.onChatBody?.(JSON.parse(req.postData() ?? "{}"));
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: CORS,
        body: sse([
          ["delta", { text: "Eat iron-rich foods with vitamin C." }],
          ["final", { answer: "Eat iron-rich foods with vitamin C.", safety_status: "safe_general", citations: [], corrected: false }],
          ["done", { conversation_id: "c1", message_id: "m1", sources: [{ id: "s1", name: "guide", title: "Guide", source_type: "government", evidence_level: "supported", review_status: "approved", extra_metadata: {} }], evidence: {}, recommendations: [], suggestions: ["Which foods should I avoid?"] }],
        ]),
      });
    }
    return route.fallback();
  });
}

test("chat is the single workspace: starters, today strip and quick actions", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/chat");
  await expect(page.getByText("What would you like to know, Asha?")).toBeVisible();
  await expect(page.getByText("Week 22 · next check-up")).toBeVisible();
  await expect(page.getByText("Around week 26")).toBeVisible();
  await expect(page.getByRole("button", { name: /Is it safe to do yoga during pregnancy/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /My week/ }).first()).toBeVisible();
});

test("retired feature pages redirect into the chat", async ({ page }) => {
  await mockBackend(page);
  for (const old of ["dashboard", "nutrition", "ayurveda", "sources", "recommendations"]) {
    await page.goto(`/${old}`);
    await expect(page).toHaveURL(/\/chat$/);
  }
});

test("a quick action and a slash command open inline cards", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/chat");
  await page.getByRole("button", { name: /My week/ }).first().click();
  await expect(page.getByRole("heading", { name: "Your week" })).toBeVisible();
  await page.getByPlaceholder(/Ask anything/).fill("/log");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Log today" })).toBeVisible();
});

test("asking a question streams the answer, follow-ups and related links", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/chat");
  await page.getByPlaceholder(/Ask anything/).fill("How do I get enough iron?");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Eat iron-rich foods with vitamin C.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Which foods should I avoid?" })).toBeVisible();
  await expect(page.getByText("Eating well in the second trimester")).toBeVisible();
});

test("the language toggle is sent with the question", async ({ page }) => {
  let body: Record<string, unknown> = {};
  await mockBackend(page, { onChatBody: (b) => (body = b) });
  await page.goto("/chat");
  await page.getByRole("button", { name: "Hindi" }).click();
  await page.getByPlaceholder(/Ask anything/).fill("आयरन कहाँ से मिलेगा");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Eat iron-rich foods with vitamin C.")).toBeVisible();
  expect(body.language).toBe("hi");
});


test("the /book card shows the book's chapters, review state and glossary", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/chat");
  await page.getByPlaceholder(/Ask anything/).fill("/book");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Anatomy Of Female Reproductive System")).toBeVisible();
  await expect(page.getByText("Approved for answers")).toBeVisible();
  await expect(page.getByText("Vagbhata")).toBeVisible();
  await page.getByPlaceholder(/Search a term/).fill("stanya");
  await expect(page.getByText("Stanya or breast milk")).toBeVisible();
});
