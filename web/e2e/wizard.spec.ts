import { expect, test } from "@playwright/test";
import path from "node:path";

import { completeValuationIntake, register, regularEmail } from "./helpers";

test("regular user uploads, selects report type, generates report, and opens viewer", async ({ page }) => {
  await register(page, regularEmail());
  await expect(page.getByText("Click or drag file here")).toBeVisible();
  await expect(page.getByText(/last 2-3 years preferred/i)).toBeVisible();
  await page.getByLabel(/business name/i).fill("E2E Holdings Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await expect(page.getByText(/sample\.pdf/i)).toBeVisible();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByRole("button", { name: /bank credit paper/i })).toBeDisabled();
  await expect(page.getByText(/advisor pilot/i).first()).toBeVisible();
  await page.getByRole("button", { name: /valuation advisory/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByText(/some profile data is incomplete/i)).toBeVisible();
  await completeValuationIntake(page);
  await page.getByRole("button", { name: /generate report/i }).click();
  await expect(page.getByText(/status:/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /open report/i })).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: /upload another/i }).click();
  await page.getByLabel(/business name/i).fill("Second E2E Holdings Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await expect(page.getByText(/sample\.pdf/i)).toBeVisible();
});

test("regular user can complete valuation-specific intake", async ({ page }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Valuation E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByText("Valuation Advisory").click();
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByLabel(/forecast horizon/i).selectOption("3");
  await page.getByLabel(/revenue growth rate/i).fill("8");
  await page.getByLabel(/terminal growth rate/i).fill("3");
  for (const name of [
    "rq_revenue_quality",
    "rq_owner_dependency",
    "rq_ebitda_growth",
    "rq_customer_concentration",
    "rq_gross_margin",
    "rq_competitive_barriers",
    "rq_growth_outlook",
    "rq_management_depth",
  ]) {
    const option = page.locator(`input[name="${name}"][value="3"]`);
    await expect(option).toHaveAttribute("required", "");
    await page.locator(`label[for="${name}-3"]`).click();
    await expect(option).toBeChecked();
  }
  await page.getByRole("button", { name: /generate report/i }).click();
  await expect(page.getByRole("link", { name: /open report/i })).toBeVisible({ timeout: 15_000 });
});
