import { expect, test } from "@playwright/test";
import { APPS, CSV_HEADER, SESSION, setupMocks } from "./helpers/mock";

test.describe("History page", () => {
  test("selecting a session loads its applications", async ({ page }) => {
    const rec = await setupMocks(page);
    await page.goto("/history");
    await expect(page.getByText("Select a session to view applications")).toBeVisible();
    await page.getByRole("button", { name: /naukri/i }).click();
    await expect(page.getByText("Senior QA Engineer")).toBeVisible();
    const calls = rec.calls("/api/history?", "GET");
    expect(calls.length).toBeGreaterThanOrEqual(1);
    expect(calls[0].path).toContain("session_id=1");
  });

  test("status filter refetches with the selected status", async ({ page }) => {
    const rec = await setupMocks(page);
    await page.goto("/history");
    await page.getByRole("button", { name: /naukri/i }).click();
    await expect(page.getByText("Senior QA Engineer")).toBeVisible();
    await page.locator("select").selectOption("applied");
    await expect.poll(() =>
      rec.calls("/api/history?", "GET").some((c) => c.path.includes("status=applied"))
    ).toBe(true);
  });

  test("Export CSV link downloads the session report with required columns", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/history");
    await page.getByRole("button", { name: /naukri/i }).click();
    const link = page.getByRole("link", { name: "Export CSV" });
    await expect(link).toHaveAttribute("href", "/api/sessions/1/report.csv");
    const text = await page.evaluate(async () =>
      (await fetch("/api/sessions/1/report.csv")).text());
    expect(text.split("\n")[0]).toBe(CSV_HEADER);
  });

  test("job title link points at the job posting", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/history");
    await page.getByRole("button", { name: /naukri/i }).click();
    await expect(page.getByRole("link", { name: /Senior QA Engineer/ }))
      .toHaveAttribute("href", "https://www.naukri.test/job-1");
  });

  test("pagination buttons call GET /api/history with the requested page", async ({ page }) => {
    const many = Array.from({ length: 20 }, (_, i) => ({ ...APPS[0], id: 100 + i }));
    const rec = await setupMocks(page, {
      "GET /api/history": { json: { total: 45, page: 1, per_page: 20, records: many } },
    });
    await page.goto("/history");
    await page.getByRole("button", { name: /naukri/i }).click();
    await expect(page.getByText("Showing 1–20 of 45")).toBeVisible();
    await page.getByRole("button", { name: "2", exact: true }).click();
    await expect.poll(() =>
      rec.calls("/api/history?", "GET").some((c) => c.path.includes("page=2"))
    ).toBe(true);
  });

  test("empty states: no sessions / no selection / no applications", async ({ page }) => {
    await setupMocks(page, {
      "GET /api/history/sessions": { json: [] },
    });
    await page.goto("/history");
    await expect(page.getByText("No sessions yet")).toBeVisible();
    await expect(page.getByText("Select a session to view applications")).toBeVisible();
  });

  test("empty applications list renders its empty state", async ({ page }) => {
    await setupMocks(page, {
      "GET /api/history/sessions": { json: [SESSION] },
      "GET /api/history": { json: { total: 0, page: 1, per_page: 20, records: [] } },
    });
    await page.goto("/history");
    await page.getByRole("button", { name: /naukri/i }).click();
    await expect(page.getByText("No applications found")).toBeVisible();
  });
});
