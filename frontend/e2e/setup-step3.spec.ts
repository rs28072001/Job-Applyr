import { expect, test } from "@playwright/test";
import type { Recorder, Overrides } from "./helpers/mock";
import { setupMocks } from "./helpers/mock";

async function gotoStep3(page, overrides: Overrides = {}): Promise<Recorder> {
  const rec = await setupMocks(page, overrides);
  await page.goto("/setup");
  await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Platform credentials" })).toBeVisible();
  return rec;
}

test.describe("Setup — Step 3 (Credentials, AI, SMTP, Launch)", () => {
  test("credential inputs accept values and passwords are masked", async ({ page }) => {
    await gotoStep3(page);
    const naukriEmail = page.locator('input[type=email]').first();
    await naukriEmail.fill("me@naukri.test");
    await expect(naukriEmail).toHaveValue("me@naukri.test");

    const pw = page.locator('input[type=password]').first();   // Naukri password
    await expect(pw).toHaveAttribute("type", "password");
    // saved password arrives masked as *** with a hint
    await expect(page.getByText("Saved locally. Paste a new password only to replace it.")).toBeVisible();
    await pw.click();                                            // focus clears the mask
    await expect(pw).toHaveValue("");
    await pw.fill("hunter2");
    await expect(pw).toHaveValue("hunter2");
  });

  test("AI provider dropdown switches the active key/model fields", async ({ page }) => {
    await gotoStep3(page);
    const model = page.getByPlaceholder("openai/gpt-oss-120b");   // groq default
    await expect(model).toHaveValue("openai/gpt-oss-120b");
    await page.locator("select").selectOption("gemini");
    await expect(page.getByPlaceholder("gemini-2.5-flash")).toBeVisible();
    await page.locator("select").selectOption("openai");
    await expect(page.getByPlaceholder("gpt-4o-mini")).toBeVisible();
  });

  test("Test connection success calls POST /api/config/test and shows the result", async ({ page }) => {
    const rec = await gotoStep3(page);
    await page.getByRole("button", { name: "Test connection" }).click();
    await expect(page.getByText("groq / openai/gpt-oss-120b: connection ok")).toBeVisible();
    expect(rec.count("/api/config/test", "POST")).toBe(1);
  });

  test("Test connection failure shows a readable error", async ({ page }) => {
    await gotoStep3(page, {
      "POST /api/config/test": {
        status: 400,
        json: { detail: { provider: "groq", model: "m", error: "Invalid API key" } },
      },
    });
    await page.getByRole("button", { name: "Test connection" }).click();
    await expect(page.getByText(/Invalid API key/)).toBeVisible();
  });

  test("Save settings calls PUT /api/config and shows Saved", async ({ page }) => {
    const rec = await gotoStep3(page);
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(page.getByRole("button", { name: "Saved ✓" })).toBeVisible();
    const puts = rec.calls("/api/config", "PUT");
    expect(puts.length).toBe(1);
    // masked secrets must never be sent back
    expect(puts[0].body.naukri_password).toBeUndefined();
    expect(puts[0].body.groq_api_key).toBeUndefined();
    expect(puts[0].body.outreach_mode).toBe("draft_only");
  });

  test("outreach mode buttons update selection; SMTP fields only for send-after-approval", async ({ page }) => {
    await gotoStep3(page);
    await expect(page.getByText("SMTP settings (your own mailbox)")).toBeHidden();

    const sendMode = page.getByRole("button", { name: /Send after approval/ });
    await sendMode.click();
    await expect(sendMode).toHaveClass(/border-indigo-400/);
    await expect(page.getByText("SMTP settings (your own mailbox)")).toBeVisible();

    await page.getByRole("button", { name: /^Off/ }).click();
    await expect(page.getByText("SMTP settings (your own mailbox)")).toBeHidden();

    const draftOnly = page.getByRole("button", { name: /Draft only/ });
    await draftOnly.click();
    await expect(draftOnly).toHaveClass(/border-indigo-400/);
  });

  test("Send test email success calls POST /api/outreach/smtp/test with the form values", async ({ page }) => {
    const rec = await gotoStep3(page);
    await page.getByRole("button", { name: /Send after approval/ }).click();
    await page.getByPlaceholder("smtp.gmail.com").fill("smtp.mailbox.test");
    await page.getByPlaceholder("you@gmail.com").first().fill("me@mailbox.test");
    await page.getByRole("button", { name: "Send test email" }).click();
    await expect(page.getByText("Test email sent to me@mailbox.test — check your inbox.")).toBeVisible();
    const calls = rec.calls("/api/outreach/smtp/test", "POST");
    expect(calls.length).toBe(1);
    expect(calls[0].body.host).toBe("smtp.mailbox.test");
  });

  test("Send test email failure shows the SMTP error", async ({ page }) => {
    await gotoStep3(page, {
      "POST /api/outreach/smtp/test": { status: 400, json: { detail: "SMTP authentication failed: bad app password" } },
    });
    await page.getByRole("button", { name: /Send after approval/ }).click();
    await page.getByRole("button", { name: "Send test email" }).click();
    await expect(page.getByText(/SMTP authentication failed/)).toBeVisible();
  });

  test("Back returns to Step 2", async ({ page }) => {
    await gotoStep3(page);
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByRole("heading", { name: "Job preferences" })).toBeVisible();
  });

  test("Launch session saves config then starts a session with the full payload", async ({ page }) => {
    const rec = await setupMocks(page);
    await page.goto("/setup");
    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();

    // customise step-2 state so we can assert it is sent through
    await page.getByPlaceholder("QA Engineer, SDET, Automation Engineer").fill("Playwright Engineer, SDET");
    await page.getByPlaceholder("gurugram").fill("pune");
    await page.locator('input[type=number]').first().fill("7");
    await page.locator('input[type=number]').nth(1).fill("80");
    await page.getByRole("button", { name: "Continue" }).click();

    await page.getByRole("button", { name: "Launch session" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    const starts = rec.calls("/api/session/start", "POST");
    expect(starts.length).toBe(1);
    const body = starts[0].body;
    expect(body.platform).toBe("naukri");
    expect(body.mode).toBe("search_and_apply");
    expect(body.location).toBe("pune");
    expect(body.job_target).toBe(7);
    expect(body.confidence_threshold).toBe(80);
    expect(body.easy_apply_only).toBe(true);
    expect(body.include_external_review).toBe(true);
    expect(body.outreach_mode).toBe("draft_only");
    expect(body.keywords).toEqual(["Playwright Engineer", "SDET"]);
    // config is saved before the session starts
    const configPut = rec.all.findIndex((c) => c.method === "PUT" && c.path.startsWith("/api/config"));
    const sessionStart = rec.all.findIndex((c) => c.method === "POST" && c.path.startsWith("/api/session/start"));
    expect(configPut).toBeGreaterThanOrEqual(0);
    expect(configPut).toBeLessThan(sessionStart);
  });

  test("Launch failure shows the error and stays on setup", async ({ page }) => {
    await gotoStep3(page, {
      "POST /api/session/start": { status: 400, json: { detail: "LLM credentials not configured. Complete setup first." } },
    });
    await page.getByRole("button", { name: "Launch session" }).click();
    await expect(page.getByText("LLM credentials not configured. Complete setup first.")).toBeVisible();
    await expect(page).toHaveURL(/\/setup$/);
  });
});
