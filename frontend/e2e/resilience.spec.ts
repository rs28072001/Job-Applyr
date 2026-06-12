import { expect, test } from "@playwright/test";
import { CONFIG, DRAFT, APPS, setupMocks, offlineBackend } from "./helpers/mock";

test.describe("Backend offline", () => {
  test("dashboard renders a stable empty state without crashing", async ({ page }) => {
    await offlineBackend(page);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
    await expect(page.getByText("No active session")).toBeVisible();
  });

  test("review page stays up", async ({ page }) => {
    await offlineBackend(page);
    await page.goto("/review");
    await expect(page.getByRole("heading", { name: "Saved & Skipped" })).toBeVisible();
  });

  test("history page stays up with empty state", async ({ page }) => {
    await offlineBackend(page);
    await page.goto("/history");
    await expect(page.getByText("No sessions yet")).toBeVisible();
  });

  test("setup page stays usable", async ({ page }) => {
    await offlineBackend(page);
    await page.goto("/setup");
    await expect(page.getByText("Upload your resume")).toBeVisible();
    await page.getByRole("button", { name: "Skip for now" }).click();
    await expect(page.getByRole("heading", { name: "Job preferences" })).toBeVisible();
  });
});

test.describe("API errors surface readable messages", () => {
  test("500 on session start", async ({ page }) => {
    await setupMocks(page, {
      "POST /api/session/start": { status: 500, json: { detail: "Internal error while starting session" } },
    });
    await page.goto("/setup");
    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Launch session" }).click();
    await expect(page.getByText("Internal error while starting session")).toBeVisible();
    await expect(page).toHaveURL(/\/setup$/);
  });

  test("500 on config test", async ({ page }) => {
    await setupMocks(page, {
      "POST /api/config/test": { status: 500, json: { detail: "LLM provider unreachable" } },
    });
    await page.goto("/setup");
    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Test connection" }).click();
    await expect(page.getByText("LLM provider unreachable")).toBeVisible();
  });

  test("500 on review resolve shows inline error and keeps the row", async ({ page }) => {
    await setupMocks(page, {
      "POST /api/review/applications/3/resolve": { status: 500, json: { detail: "Database is locked" } },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "I applied" }).click();
    await expect(page.getByText("Database is locked")).toBeVisible();
    await expect(page.getByText("QA Automation Lead")).toBeVisible();
  });

  test("500 on draft approve shows inline error", async ({ page }) => {
    await setupMocks(page, {
      "POST /api/outreach/11/approve": { status: 500, json: { detail: "Draft store unavailable" } },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("Draft store unavailable")).toBeVisible();
  });
});

test.describe("Slow responses and duplicate-click protection", () => {
  test("slow config test shows spinner and blocks duplicate submissions", async ({ page }) => {
    const rec = await setupMocks(page, {
      "POST /api/config/test": {
        delayMs: 1200,
        json: { ok: true, provider: "groq", model: "m", output: "ok" },
      },
    });
    await page.goto("/setup");
    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    const btn = page.getByRole("button", { name: "Test connection" });
    await btn.click();
    const busy = page.getByRole("button", { name: "Testing…" });
    await expect(busy).toBeDisabled();
    await busy.click({ force: true }).catch(() => {});  // hammering does nothing
    await expect(page.getByText(/connection ok|: ok/)).toBeVisible();
    expect(rec.count("/api/config/test", "POST")).toBe(1);
  });

  test("double-click on Launch session starts exactly one session", async ({ page }) => {
    const rec = await setupMocks(page, {
      "POST /api/session/start": { delayMs: 800, json: { status: "started", session_id: 2 } },
    });
    await page.goto("/setup");
    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    const launch = page.getByRole("button", { name: "Launch session" });
    await launch.click();
    await page.getByRole("button", { name: "Starting…" }).click({ force: true }).catch(() => {});
    await expect(page).toHaveURL(/\/dashboard$/);
    expect(rec.count("/api/session/start", "POST")).toBe(1);
  });

  test("double-click on Stop sends exactly one stop request", async ({ page }) => {
    const rec = await setupMocks(page, {
      "GET /api/session/status": {
        json: { is_running: true, session_id: 1, started_at: null, counts: {}, session: null },
      },
      "POST /api/session/stop": { delayMs: 800, json: { status: "stopped" } },
    });
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Stop session" }).click();
    // optimistic stop removes the button immediately — a second click is impossible
    await expect(page.getByRole("button", { name: /Stop session|Stopping/ })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "New session" })).toBeVisible();
    await expect.poll(() => rec.count("/api/session/stop", "POST")).toBe(1);
    await page.waitForTimeout(1000);   // give a hypothetical duplicate time to appear
    expect(rec.count("/api/session/stop", "POST")).toBe(1);
  });

  test("double-click on Save settings sends one PUT", async ({ page }) => {
    const rec = await setupMocks(page, {
      "PUT /api/config": { delayMs: 800, json: { status: "saved", is_configured: true } },
    });
    await page.goto("/setup");
    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Save settings" }).click();
    await page.getByRole("button", { name: "Saving…" }).click({ force: true }).catch(() => {});
    await expect(page.getByRole("button", { name: "Saved ✓" })).toBeVisible();
    expect(rec.count("/api/config", "PUT")).toBe(1);
  });

  test("double-click on Approve / Discard sends one request each", async ({ page }) => {
    const rec = await setupMocks(page, {
      "POST /api/outreach/11/approve": {
        delayMs: 700, json: { ...DRAFT, status: "approved" },
      },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "Approve" }).click();
    // while busy, all draft action buttons are disabled
    await expect(page.getByRole("button", { name: "Discard" })).toBeDisabled();
    await page.getByRole("button", { name: "Approve" }).click({ force: true }).catch(() => {});
    await page.waitForTimeout(1000);
    expect(rec.count("/api/outreach/11/approve", "POST")).toBe(1);
    expect(rec.count("/api/outreach/11/discard", "POST")).toBe(0);
  });
});

test.describe("Reload preserves routes", () => {
  for (const route of ["/dashboard", "/setup", "/review", "/history"]) {
    test(`reload on ${route} stays on ${route}`, async ({ page }) => {
      await setupMocks(page);
      await page.goto(route);
      await page.reload();
      await expect(page).toHaveURL(new RegExp(`${route}$`));
      await expect(page.locator("aside, nav").first()).toBeVisible();
    });
  }
});
