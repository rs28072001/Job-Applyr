import { expect, test } from "@playwright/test";
import { setupMocks } from "./helpers/mock";

async function gotoStep2(page) {
  await page.goto("/setup");
  await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
  await expect(page.getByRole("heading", { name: "Job preferences" })).toBeVisible();
}

test.describe("Setup — Step 2 (Preferences)", () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await gotoStep2(page);
  });

  test("platform buttons update selected state", async ({ page }) => {
    for (const p of ["linkedin", "both", "naukri"]) {
      const btn = page.getByRole("button", { name: p, exact: true });
      await btn.click();
      await expect(btn).toHaveClass(/bg-indigo-600/);
    }
  });

  test("mode buttons update selected state", async ({ page }) => {
    const searchOnly = page.getByRole("button", { name: "Search only" });
    await searchOnly.click();
    await expect(searchOnly).toHaveClass(/bg-indigo-600/);
    const searchApply = page.getByRole("button", { name: "Search & Apply" });
    await searchApply.click();
    await expect(searchApply).toHaveClass(/bg-indigo-600/);
  });

  test("target keywords input persists typed keywords", async ({ page }) => {
    const kw = page.getByPlaceholder("QA Engineer, SDET, Automation Engineer");
    await expect(kw).toHaveValue(/QA Engineer/);   // pre-filled from resume
    await kw.fill("Playwright Engineer, SDET");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByPlaceholder("QA Engineer, SDET, Automation Engineer"))
      .toHaveValue("Playwright Engineer, SDET");
  });

  test("location input persists typed value", async ({ page }) => {
    await page.getByPlaceholder("gurugram").fill("pune");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByPlaceholder("gurugram")).toHaveValue("pune");
  });

  test("target jobs and min score inputs enforce numeric bounds", async ({ page }) => {
    const target = page.locator('input[type=number]').first();
    await expect(target).toHaveAttribute("min", "1");
    await expect(target).toHaveAttribute("max", "100");
    await target.fill("7");
    await expect(target).toHaveValue("7");

    const minScore = page.locator('input[type=number]').nth(1);
    await expect(minScore).toHaveAttribute("min", "0");
    await expect(minScore).toHaveAttribute("max", "100");
    await minScore.fill("80");
    await expect(minScore).toHaveValue("80");
  });

  test("Easy Apply toggle changes state and survives step navigation", async ({ page }) => {
    const toggle = page.getByRole("button", { name: /Easy Apply only/ });
    await expect(toggle.locator("span").first()).toHaveClass(/bg-indigo-600/); // default ON
    await toggle.click();
    await expect(toggle.locator("span").first()).toHaveClass(/bg-slate-200/);
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByRole("button", { name: /Easy Apply only/ }).locator("span").first())
      .toHaveClass(/bg-slate-200/);
  });

  test("save-external-jobs toggle changes state and survives step navigation", async ({ page }) => {
    const toggle = page.getByRole("button", { name: /Save external company-site jobs/ });
    await expect(toggle.locator("span").first()).toHaveClass(/bg-indigo-600/); // default ON
    await toggle.click();
    await expect(toggle.locator("span").first()).toHaveClass(/bg-slate-200/);
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByRole("button", { name: /Save external company-site jobs/ }).locator("span").first())
      .toHaveClass(/bg-slate-200/);
  });

  test("Back returns to Step 1 and Continue moves to Step 3", async ({ page }) => {
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByText("Upload your resume")).toBeVisible();
    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByRole("heading", { name: "Platform credentials" })).toBeVisible();
  });
});
