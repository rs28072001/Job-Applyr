import { expect, test } from "@playwright/test";
import type { Route } from "@playwright/test";
import { APPS, CONFIG, DRAFT, setupMocks } from "./helpers/mock";

const QUEUE = { manual_review: [], drafts: [DRAFT],
                skipped: [APPS[3], APPS[4]], saved: [APPS[2]] };

function jsonRoute(data: () => unknown) {
  return async (route: Route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify(data()) });
}

test.describe("Saved & Skipped page", () => {
  test("loads GET /api/review/queue and renders all sections", async ({ page }) => {
    const rec = await setupMocks(page);
    await page.goto("/review");
    await expect(page.getByText("QA Automation Lead")).toBeVisible();   // saved job
    await expect(page.getByText("Saved automatically — apply on the company site whenever you like")).toBeVisible();
    await expect(page.getByText("Nothing needs attention")).toBeVisible();
    await expect(page.getByText("Recently skipped")).toBeVisible();
    await expect(page.getByText("QA Engineer (Contract)", { exact: true })).toBeVisible();
    expect(rec.count("/api/review/queue", "GET")).toBeGreaterThanOrEqual(1);
  });

  test("saved-job Open button carries the external URL", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/review");
    await expect(page.getByRole("link", { name: "Open", exact: true }))
      .toHaveAttribute("href", "https://careers.megacorp.test/jobs/77");
  });

  test("'I applied' posts mark_applied and the saved row disappears after refresh", async ({ page }) => {
    let resolved = false;
    const rec = await setupMocks(page, {
      "GET /api/review/queue": jsonRoute(() =>
        resolved ? { ...QUEUE, saved: [] } : QUEUE),
      "POST /api/review/applications/3/resolve": async (route) => {
        resolved = true;
        await route.fulfill({ contentType: "application/json", body: '{"status":"applied"}' });
      },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "I applied" }).click();
    await expect(page.getByText("QA Automation Lead")).toBeHidden();
    await expect(page.getByText("No saved jobs yet")).toBeVisible();
    const calls = rec.calls("/api/review/applications/3/resolve", "POST");
    expect(calls.length).toBe(1);
    expect(calls[0].body).toEqual({ action: "mark_applied" });
  });

  test("'Remove' posts dismiss and the saved row disappears after refresh", async ({ page }) => {
    let resolved = false;
    const rec = await setupMocks(page, {
      "GET /api/review/queue": jsonRoute(() =>
        resolved ? { ...QUEUE, saved: [] } : QUEUE),
      "POST /api/review/applications/3/resolve": async (route) => {
        resolved = true;
        await route.fulfill({ contentType: "application/json", body: '{"status":"skipped"}' });
      },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "Remove" }).click();
    await expect(page.getByText("QA Automation Lead")).toBeHidden();
    expect(rec.calls("/api/review/applications/3/resolve", "POST")[0].body)
      .toEqual({ action: "dismiss" });
  });

  test("skipped rows show — for unscored jobs and a clear skip reason", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/review");
    const mismatch = page.locator("div", { hasText: "Sales Executive" }).locator("..").last();
    await expect(page.getByText("Title mismatch")).toBeVisible();
    await expect(page.getByText("Low score")).toBeVisible();
    // unscored row renders an em-dash, scored row renders its score
    await expect(page.getByText("—", { exact: true })).toBeVisible();
    await expect(page.getByText("58", { exact: true })).toBeVisible();
  });
});

test.describe("Email draft actions", () => {
  test("Approve calls POST approve and shows Approved state", async ({ page }) => {
    let approved = false;
    const rec = await setupMocks(page, {
      "GET /api/review/queue": jsonRoute(() => approved
        ? { ...QUEUE, drafts: [{ ...DRAFT, status: "approved" }] } : QUEUE),
      "POST /api/outreach/11/approve": async (route) => {
        approved = true;
        await route.fulfill({ contentType: "application/json",
                              body: JSON.stringify({ ...DRAFT, status: "approved" }) });
      },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("Approved — ready")).toBeVisible();
    expect(rec.count("/api/outreach/11/approve", "POST")).toBe(1);
  });

  test("Edit opens subject/body fields; Save calls PUT and exits edit mode", async ({ page }) => {
    const rec = await setupMocks(page);
    await page.goto("/review");
    await page.getByRole("button", { name: "Edit" }).click();
    const subject = page.locator('input[value*="Application for QA Engineer"]');
    await expect(subject).toBeVisible();
    await subject.fill("Updated subject line");
    await page.locator("textarea").fill("Updated body text for the recruiter.");
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.locator("textarea")).toBeHidden();   // edit mode closed
    const puts = rec.calls("/api/outreach/11", "PUT");
    expect(puts.length).toBe(1);
    expect(puts[0].body).toEqual({ subject: "Updated subject line",
                                   body: "Updated body text for the recruiter." });
  });

  test("Cancel exits edit mode and restores the original subject/body", async ({ page }) => {
    const rec = await setupMocks(page);
    await page.goto("/review");
    await page.getByRole("button", { name: "Edit" }).click();
    await page.locator('input[value*="Application for QA Engineer"]').fill("Scratch this");
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.locator("textarea")).toBeHidden();
    await expect(page.getByText("Application for QA Engineer (Contract) — Sumit Tiwari")).toBeVisible();
    await expect(page.getByText("Scratch this")).toBeHidden();
    expect(rec.count("/api/outreach/11", "PUT")).toBe(0);
  });

  test("Copy writes recipient, subject, and body to the clipboard and shows Copied", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/review");
    await page.getByRole("button", { name: "Copy", exact: true }).click();
    await expect(page.getByText("Copied!")).toBeVisible();
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    expect(clip).toContain("To: priya@startupxyz.test");
    expect(clip).toContain("Subject: Application for QA Engineer (Contract) — Sumit Tiwari");
    expect(clip).toContain("Dear Hiring Team,");
  });

  test("'Open in mail app' is a mailto link with subject and body", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/review");
    const href = await page.getByRole("link", { name: "Open in mail app" }).getAttribute("href");
    expect(href).toContain("mailto:priya@startupxyz.test");
    expect(href).toContain(`subject=${encodeURIComponent(DRAFT.subject)}`);
    expect(href).toContain(encodeURIComponent("Dear Hiring Team,"));
  });

  test("'I sent it' calls mark_sent and the draft leaves the queue", async ({ page }) => {
    let sent = false;
    const rec = await setupMocks(page, {
      "GET /api/review/queue": jsonRoute(() => sent ? { ...QUEUE, drafts: [] } : QUEUE),
      "POST /api/outreach/11/mark_sent": async (route) => {
        sent = true;
        await route.fulfill({ contentType: "application/json",
                              body: JSON.stringify({ ...DRAFT, status: "sent" }) });
      },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "I sent it" }).click();
    await expect(page.getByText("No drafts yet")).toBeVisible();
    expect(rec.count("/api/outreach/11/mark_sent", "POST")).toBe(1);
  });

  test("Send via SMTP is hidden in draft_only mode and for unapproved drafts", async ({ page }) => {
    await setupMocks(page);   // draft_only + status draft
    await page.goto("/review");
    await expect(page.getByText("QA Engineer (Contract)", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Send via SMTP" })).toHaveCount(0);
  });

  test("Send via SMTP appears for approved drafts in send_after_approval mode and sends", async ({ page }) => {
    let sent = false;
    const rec = await setupMocks(page, {
      "GET /api/config": { json: { ...CONFIG, outreach_mode: "send_after_approval" } },
      "GET /api/review/queue": jsonRoute(() => sent
        ? { ...QUEUE, drafts: [] }
        : { ...QUEUE, drafts: [{ ...DRAFT, status: "approved" }] }),
      "POST /api/outreach/11/send": async (route) => {
        sent = true;
        await route.fulfill({ contentType: "application/json",
                              body: JSON.stringify({ ...DRAFT, status: "sent" }) });
      },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "Send via SMTP" }).click();
    await expect(page.getByText("No drafts yet")).toBeVisible();
    expect(rec.count("/api/outreach/11/send", "POST")).toBe(1);
  });

  test("Send via SMTP failure shows a readable SMTP error", async ({ page }) => {
    await setupMocks(page, {
      "GET /api/config": { json: { ...CONFIG, outreach_mode: "send_after_approval" } },
      "GET /api/review/queue": { json: { ...QUEUE, drafts: [{ ...DRAFT, status: "approved" }] } },
      "POST /api/outreach/11/send": {
        status: 400,
        json: { detail: "SMTP is not configured. Add SMTP settings, or copy the draft and send it from your own mail client." },
      },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "Send via SMTP" }).click();
    await expect(page.getByText(/SMTP is not configured/)).toBeVisible();
  });

  test("Discard calls POST discard and removes the draft", async ({ page }) => {
    let discarded = false;
    const rec = await setupMocks(page, {
      "GET /api/review/queue": jsonRoute(() => discarded ? { ...QUEUE, drafts: [] } : QUEUE),
      "POST /api/outreach/11/discard": async (route) => {
        discarded = true;
        await route.fulfill({ contentType: "application/json",
                              body: JSON.stringify({ ...DRAFT, status: "discarded" }) });
      },
    });
    await page.goto("/review");
    await page.getByRole("button", { name: "Discard" }).click();
    await expect(page.getByText("No drafts yet")).toBeVisible();
    expect(rec.count("/api/outreach/11/discard", "POST")).toBe(1);
  });
});
