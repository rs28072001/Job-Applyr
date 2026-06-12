import { expect, test } from "@playwright/test";
import { APPS, CSV_HEADER, SESSION, STATUS_COUNTS, setupMocks } from "./helpers/mock";

// the app shell sidebar is also an <aside>; the drawer is the fixed one
const DRAWER = "aside.fixed";

test.describe("Dashboard", () => {
  test("New session button navigates to /setup when idle", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "New session" }).click();
    await expect(page).toHaveURL(/\/setup$/);
  });

  test("Stop session calls POST /api/session/stop, shows stopping state, banner becomes Stopped", async ({ page }) => {
    const rec = await setupMocks(page, {
      "GET /api/session/status": {
        json: { is_running: true, session_id: 1, started_at: "2026-06-11T10:00:00Z",
                counts: STATUS_COUNTS, session: { ...SESSION, status: "running" } },
      },
      "POST /api/session/stop": { delayMs: 600, json: { status: "stopped" } },
    });
    await page.goto("/dashboard");
    const stop = page.getByRole("button", { name: "Stop session" });
    await expect(stop).toBeVisible();
    await stop.click();
    // stop is optimistic: UI flips to stopped immediately and the stop call fires
    await expect(page.getByText("Stopped", { exact: true }).first()).toBeVisible();  // banner
    await expect(page.getByRole("link", { name: "New session" })).toBeVisible();
    await expect.poll(() => rec.count("/api/session/stop", "POST")).toBe(1);
  });

  test("in-flight job rows become stopped after Stop", async ({ page }) => {
    await setupMocks(page, {
      "GET /api/session/status": {
        json: { is_running: true, session_id: 1, started_at: null,
                counts: STATUS_COUNTS, session: { ...SESSION, status: "running" } },
      },
      // hydrated table contains an in-flight row
      "GET /api/history": {
        json: { total: 1, page: 1, per_page: 100,
                records: [{ ...APPS[0], id: 99, job_title: "InFlight Job", status: "applying" }] },
      },
    });
    await page.goto("/dashboard");
    await expect(page.getByText("InFlight Job")).toBeVisible();
    await page.getByRole("button", { name: "Stop session" }).click();
    await expect(page.getByText("Stopped", { exact: true }).first()).toBeVisible();
  });

  test("Export report downloads CSV with the required columns", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
    const link = page.getByRole("link", { name: "Export report" });
    await expect(link).toHaveAttribute("href", "/api/sessions/1/report.csv");
    // fetch through the page so the mocked route serves the file content
    const text = await page.evaluate(async () =>
      (await fetch("/api/sessions/1/report.csv")).text());
    expect(text.split("\n")[0]).toBe(CSV_HEADER);
    expect(text).toContain("Senior QA Engineer");
    // the link itself triggers a browser download (download attribute present)
    await expect(link).toHaveAttribute("download", "");
  });

  test("job row click opens the detail drawer; X and backdrop close it", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /Senior QA Engineer/ }).click();
    const drawer = page.locator(DRAWER);
    await expect(drawer.getByText("Senior QA Engineer")).toBeVisible();

    await page.getByRole("button", { name: "Close details" }).click();
    await expect(page.locator(DRAWER)).toBeHidden();

    await page.getByRole("button", { name: /Senior QA Engineer/ }).click();
    await expect(page.locator(DRAWER)).toBeVisible();
    await page.getByTestId("drawer-backdrop").click({ position: { x: 10, y: 10 } });
    await expect(page.locator(DRAWER)).toBeHidden();
  });

  test("row external-link icon has the job href and does not open the drawer", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
    const row = page.getByRole("button", { name: /Senior QA Engineer/ });
    const icon = row.getByRole("link", { name: "Open job posting" });
    await expect(icon).toHaveAttribute("href", "https://www.naukri.test/job-1");
    await expect(icon).toHaveAttribute("target", "_blank");
    const [popup] = await Promise.all([
      page.waitForEvent("popup"),
      icon.click(),
    ]);
    await popup.close();
    await expect(page.locator(DRAWER)).toBeHidden();   // drawer never opened
  });

  test("Needs Attention card link navigates to /review", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Open →" }).click();
    await expect(page).toHaveURL(/\/review$/);
  });

  test("email draft hint link navigates to /review", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "View drafts →" }).click();
    await expect(page).toHaveURL(/\/review$/);
  });

  test("alerts render for broken selectors, missing SMTP, and high failure rate", async ({ page }) => {
    await setupMocks(page, {
      "GET /api/alerts": {
        json: { alerts: [
          { id: "selectors_broken", severity: "error",
            title: "Selector health check failing", detail: "Broken groups: naukri/apply." },
          { id: "smtp_missing", severity: "warning",
            title: "Outreach mode is 'send after approval' but SMTP is not ready",
            detail: "SMTP host is empty." },
          { id: "high_failure_rate", severity: "error",
            title: "High failure rate in last session (4/7 failed)", detail: "Check failure reasons." },
        ] },
      },
    });
    await page.goto("/dashboard");
    await expect(page.getByText("Selector health check failing")).toBeVisible();
    await expect(page.getByText(/SMTP is not ready/)).toBeVisible();
    await expect(page.getByText(/High failure rate in last session/)).toBeVisible();
  });
});

test.describe("Job detail drawer content", () => {
  test("shows status, classification, score, rationale, skills, salary, experience", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /Senior QA Engineer/ }).click();
    const drawer = page.locator(DRAWER);
    await expect(drawer.getByText("Senior QA Engineer")).toBeVisible();
    await expect(drawer.getByText("TechCorp")).toBeVisible();
    await expect(drawer.getByText("Applied", { exact: true })).toBeVisible();
    await expect(drawer.getByText("Internal apply")).toBeVisible();
    await expect(drawer.getByText("88", { exact: true })).toBeVisible();
    await expect(drawer.getByText("Strong overlap.")).toBeVisible();
    await expect(drawer.getByText("Selenium", { exact: true })).toBeVisible();   // matched
    await expect(drawer.getByText("Rust", { exact: true })).toBeVisible();       // missing
    await expect(drawer.getByText("12-18 LPA")).toBeVisible();
    await expect(drawer.getByText("3-6 Yrs")).toBeVisible();
    await expect(drawer.getByRole("link", { name: "Open job" }))
      .toHaveAttribute("href", "https://www.naukri.test/job-1");
  });

  test("shows company-site link when external_site_url is present", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /QA Automation Lead/ }).click();
    const drawer = page.locator(DRAWER);
    await expect(drawer.getByText("Saved", { exact: true })).toBeVisible();
    await expect(drawer.getByText("External company site")).toBeVisible();   // reason label
    await expect(drawer.getByRole("link", { name: "Company site" }))
      .toHaveAttribute("href", "https://careers.megacorp.test/jobs/77");
  });
});
