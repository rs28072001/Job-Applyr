import { expect, test } from "@playwright/test";
import { setupMocks } from "./helpers/mock";

const PDF = {
  name: "resume.pdf",
  mimeType: "application/pdf",
  buffer: Buffer.from("%PDF-1.4 fake resume for tests"),
};
const TXT = {
  name: "resume.txt",
  mimeType: "text/plain",
  buffer: Buffer.from("not a pdf"),
};

test.describe("Setup — Step 1 (Resume)", () => {
  test("PDF upload calls POST /api/cv/parse and shows the parsed preview", async ({ page }) => {
    const rec = await setupMocks(page);
    await page.goto("/setup");
    await page.locator("input[type=file]").setInputFiles(PDF);
    await expect(page.getByText("Resume parsed")).toBeVisible();
    await expect(page.getByText("Sumit Tiwari")).toBeVisible();
    await expect(page.getByText("Selenium", { exact: true })).toBeVisible();
    expect(rec.count("/api/cv/parse", "POST")).toBe(1);
  });

  test("non-PDF upload shows a validation error and never calls the parse API", async ({ page }) => {
    const rec = await setupMocks(page);
    await page.goto("/setup");
    await page.locator("input[type=file]").setInputFiles(TXT);
    await expect(page.getByText("Please upload a PDF file")).toBeVisible();
    expect(rec.count("/api/cv/parse", "POST")).toBe(0);
  });

  test("Continue moves to Step 2 (existing profile)", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/setup");
    // existing profile is loaded from GET /api/cv/profile → button says Continue
    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
    await expect(page.getByRole("heading", { name: "Job preferences" })).toBeVisible();
  });

  test("Skip for now moves to Step 2 when no profile exists", async ({ page }) => {
    await setupMocks(page, { "GET /api/cv/profile": { status: 404, json: { detail: "none" } } });
    await page.goto("/setup");
    await page.getByRole("button", { name: "Skip for now" }).click();
    await expect(page.getByRole("heading", { name: "Job preferences" })).toBeVisible();
  });

  test("stepper only allows reachable steps", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/setup");
    // Steps 2 and 3 unreachable before visiting them
    await expect(page.getByRole("button", { name: "2. Job preferences" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "3. Credentials & launch" })).toBeDisabled();

    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();
    await expect(page.getByRole("button", { name: "2. Job preferences" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "3. Credentials & launch" })).toBeDisabled();

    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByRole("button", { name: "3. Credentials & launch" })).toBeEnabled();

    // stepper buttons navigate back to any reached step
    await page.getByRole("button", { name: "1. Resume" }).click();
    await expect(page.getByText("Upload your resume")).toBeVisible();
  });

  test("step navigation keeps entered state", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/setup");
    await page.getByRole("button", { name: /Continue|Skip for now/ }).click();

    const location = page.getByPlaceholder("gurugram");
    await location.fill("bengaluru");
    await page.getByRole("button", { name: "1. Resume" }).click();   // back via stepper
    await page.getByRole("button", { name: "2. Job preferences" }).click();
    await expect(page.getByPlaceholder("gurugram")).toHaveValue("bengaluru");
  });
});
