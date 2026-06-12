import { expect, test } from "@playwright/test";
import { setupMocks } from "./helpers/mock";

test.describe("Sidebar / global navigation", () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
  });

  test("Dashboard button navigates to /dashboard and shows Command Center", async ({ page }) => {
    await page.goto("/history");
    await page.getByRole("link", { name: "Dashboard" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  });

  test("Setup button navigates to /setup and shows the 3-step flow", async ({ page }) => {
    await page.getByRole("link", { name: "Setup", exact: true }).click();
    await expect(page).toHaveURL(/\/setup$/);
    await expect(page.getByText("Three steps: resume → preferences → credentials & launch")).toBeVisible();
    await expect(page.getByRole("button", { name: "1. Resume" })).toBeVisible();
  });

  test("Saved & Skipped button navigates to /review", async ({ page }) => {
    await page.getByRole("link", { name: "Saved & Skipped" }).click();
    await expect(page).toHaveURL(/\/review$/);
    await expect(page.getByRole("heading", { name: "Saved & Skipped" })).toBeVisible();
    await expect(page.getByText("Saved jobs (external sites)")).toBeVisible();
    await expect(page.getByText("Needs attention", { exact: true })).toBeVisible();
    await expect(page.getByText("Recently skipped")).toBeVisible();
  });

  test("History button navigates to /history and shows sessions UI", async ({ page }) => {
    await page.getByRole("link", { name: "History" }).click();
    await expect(page).toHaveURL(/\/history$/);
    await expect(page.getByRole("heading", { name: "History" })).toBeVisible();
    await expect(page.getByText("Sessions", { exact: true })).toBeVisible();
  });
});

test.describe("Theme toggle", () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto("/dashboard");
  });

  test("dark mode applies the DOM class and persists after reload", async ({ page }) => {
    const html = page.locator("html");
    await expect(html).not.toHaveClass(/dark/);

    await page.getByRole("radio", { name: "Dark" }).click();
    await expect(html).toHaveClass(/dark/);

    await page.reload();
    await expect(html).toHaveClass(/dark/);
    await expect(page.getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
  });

  test("light mode removes the dark class and persists", async ({ page }) => {
    await page.getByRole("radio", { name: "Dark" }).click();
    await page.getByRole("radio", { name: "Light" }).click();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
    await page.reload();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });

  test("system mode follows the OS color scheme", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.getByRole("radio", { name: "System" }).click();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await page.emulateMedia({ colorScheme: "light" });
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });

  test("cycling all three modes updates the selected control", async ({ page }) => {
    for (const mode of ["Light", "Dark", "System"]) {
      await page.getByRole("radio", { name: mode }).click();
      await expect(page.getByRole("radio", { name: mode })).toHaveAttribute("aria-checked", "true");
    }
  });
});
