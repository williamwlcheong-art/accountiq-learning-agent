import { expect, test } from "@playwright/test";
import path from "node:path";

import { approvePendingReport, completeValuationIntake, loginOrRegisterAdmin } from "./helpers";

test("provisioned admin can use admin workflows", async ({ page }) => {
  await loginOrRegisterAdmin(page);
  await expect(page).toHaveURL(/\/admin$/);

  await page.getByRole("link", { name: /companies/i }).click();
  await page.getByRole("button", { name: /add company/i }).click();
  await page.getByLabel(/company name/i).fill("Admin E2E Ltd");
  await page.getByLabel(/sector/i).fill("Professional Services");
  await page.getByRole("button", { name: /save company/i }).click();
  await expect(page.getByText("Admin E2E Ltd")).toBeVisible();

  await page.getByRole("button", { name: /edit profile/i }).click();
  await expect(page.getByRole("heading", { name: /business profile/i })).toBeVisible();
  await page.getByLabel(/business description/i).fill(
    "Professional services company with recurring advisory revenue, a diversified customer base, and a stable operating footprint.",
  );
  await page.getByRole("button", { name: /save profile/i }).click();
  await expect(page.getByText(/business profile saved/i)).toBeVisible();
  await page.getByLabel(/^name$/i).fill("Jane Smith");
  await page.getByLabel(/title/i).fill("Managing Director");
  await page.getByLabel(/bio/i).fill("Leads operations and client delivery.");
  await page.getByRole("button", { name: /add member/i }).click();
  await expect(page.getByText(/team member added/i)).toBeVisible();
  await page.getByLabel(/^label$/i).fill("Owner salary above market");
  await page.getByLabel(/amount/i).fill("80000");
  await page.getByLabel(/rationale/i).fill("Normalise owner remuneration to market level.");
  await page.getByRole("button", { name: /add adjustment/i }).click();
  await expect(page.getByText(/adjustment added/i)).toBeVisible();
  await expect(page.locator("tr").filter({ hasText: "Admin E2E Ltd" }).getByText("4/4 complete")).toBeVisible();

  await page.getByRole("link", { name: /upload pdf/i }).click();
  await expect(page.getByText(/uploading for: admin e2e ltd/i)).toBeVisible();
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /upload/i }).click();
  await expect(page.getByText("done")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: /documents/i }).click();
  await expect(page.getByText("sample.pdf")).toBeVisible();

  await page.getByRole("link", { name: /financials/i }).click();
  await expect(page.getByText(/revenue/i)).toBeVisible({ timeout: 15_000 });

  await page.goto("/wizard");
  await page.getByLabel(/business name/i).fill("Admin Review E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByRole("button", { name: /valuation advisory/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await completeValuationIntake(page);
  await page.getByRole("button", { name: /generate report/i }).click();
  await expect(page.getByText(/your report is under review/i)).toBeVisible({ timeout: 15_000 });

  await approvePendingReport(page, "Admin Review E2E Ltd");
});
