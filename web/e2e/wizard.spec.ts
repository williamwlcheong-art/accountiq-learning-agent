import { expect, test } from "@playwright/test";
import path from "node:path";

import { approvePendingReport, completeValuationIntake, loginOrRegisterAdmin, register, regularEmail } from "./helpers";

test("regular user uploads, selects report type, generates report, and reaches reviewed release", async ({ page, browser }) => {
  await register(page, regularEmail());
  await expect(page.getByText("Click or drag file here")).toBeVisible();
  await expect(page.getByText(/last 2-3 years preferred/i)).toBeVisible();
  await page.getByLabel(/business name/i).fill("E2E Holdings Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await expect(page.getByText(/sample\.pdf/i)).toBeVisible();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByText(/ready for valuation intake/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/sample\.pdf/i).first()).toBeVisible();
  await expect(page.getByText(/\$495\.00/i)).toBeVisible();
  await page.getByRole("button", { name: /continue to report/i }).click();
  await expect(page.getByRole("button", { name: /bank credit paper/i })).toBeDisabled();
  await expect(page.getByText(/advisor pilot/i).first()).toBeVisible();
  await page.getByRole("button", { name: /valuation advisory/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByText(/some profile data is incomplete/i)).toBeVisible();
  await completeValuationIntake(page);
  await page.getByRole("button", { name: /review and continue/i }).click();
  await expect(page.getByRole("heading", { name: /confirm your valuation order/i })).toBeVisible();
  await expect(page.getByText(/inputs are frozen/i)).toBeVisible();
  await expect(page.getByText(/human review/i)).toBeVisible();
  const checkoutResponse = page.waitForResponse((response) =>
    response.url().includes("/wizard/report/checkout") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: /proceed to secure checkout/i }).click();
  await expect((await checkoutResponse).status()).toBe(201);
  await expect(page.getByText(/status:/i)).toBeVisible();
  await expect(page.getByText(/your report is under review/i)).toBeVisible({ timeout: 15_000 });
  await page.reload();
  await expect(page.getByText(/your report is under review/i)).toBeVisible({ timeout: 15_000 });

  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  await loginOrRegisterAdmin(adminPage);
  await approvePendingReport(adminPage, "E2E Holdings Ltd");
  await adminContext.close();

  await expect(page.getByRole("link", { name: /open report/i })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("link", { name: /download pdf/i })).toBeVisible();
  await page.getByRole("button", { name: /upload another/i }).click();
  await page.getByLabel(/business name/i).fill("Second E2E Holdings Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await expect(page.getByText(/sample\.pdf/i)).toBeVisible();
});

test("checkout clarification confirms no payment and allows restart", async ({ page }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Clarification E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByText(/ready for valuation intake/i)).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: /continue to report/i }).click();
  await page.getByText("Valuation Advisory").click();
  await page.getByRole("button", { name: /continue/i }).click();
  await completeValuationIntake(page);
  await page.getByRole("button", { name: /review and continue/i }).click();

  await page.route("**/wizard/report/checkout", async (route) => {
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        detail: {
          state: "needs_clarification",
          code: "needs_clarification",
          reason_code: "incompatible_balance_sheet_period",
          message: "A balance sheet matching the selected fiscal year-end is required.",
          details: { base_period: "2025", balance_sheet_periods: ["2023", "2024"] },
        },
      }),
    });
  });
  await page.getByRole("button", { name: /proceed to secure checkout/i }).click();
  await expect(page.getByText(/no payment was taken/i)).toBeVisible();
  await expect(page.getByText(/base period/i)).toBeVisible();
  await expect(page.getByText("2025")).toBeVisible();
  await expect(page.getByText("2023, 2024")).toBeVisible();
  await page.getByRole("button", { name: /upload different statements/i }).click();
  await expect(page.getByRole("heading", { name: /upload your financial statements/i })).toBeVisible();
});


test("regular user can complete valuation-specific intake", async ({ page }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Valuation E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByText(/ready for valuation intake/i)).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: /continue to report/i }).click();
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
  await page.getByRole("button", { name: /review and continue/i }).click();
  await expect(page.getByRole("heading", { name: /confirm your valuation order/i })).toBeVisible();
  const checkoutResponse = page.waitForResponse((response) =>
    response.url().includes("/wizard/report/checkout") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: /proceed to secure checkout/i }).click();
  await expect((await checkoutResponse).status()).toBe(201);
  await expect(page.getByText(/your report is under review/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("link", { name: /open report/i })).toHaveCount(0);
});
