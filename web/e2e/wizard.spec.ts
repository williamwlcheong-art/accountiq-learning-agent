import { expect, test } from "@playwright/test";
import path from "node:path";

import { approvePendingReport, completeValuationIntake, loginOrRegisterAdmin, register, regularEmail } from "./helpers";

test("regular user uploads, selects report type, generates report, and reaches reviewed release", async ({ page, browser }) => {
  const companyName = `E2E Holdings Ltd ${Date.now()}`;
  await register(page, regularEmail());
  await expect(page.getByText("Click or drag file here")).toBeVisible();
  await expect(page.getByText(/last 2-3 years preferred/i)).toBeVisible();
  await expect(page.locator(".wizard-phase")).toHaveText("Financial statements");
  await page.getByRole("link", { name: "Account", exact: true }).click();
  await expect(page).toHaveURL(/\/account$/);
  await page.getByLabel("Customer navigation").getByRole("link", { name: "New valuation", exact: true }).click();
  await expect(page).toHaveURL(/\/wizard$/);
  await page.getByLabel(/business name/i).fill(companyName);
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await expect(page.getByText(/sample\.pdf/i)).toBeVisible();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByText(/ready for valuation intake/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".wizard-phase")).toHaveText("Financial statements");
  await expect(page.getByText(/sample\.pdf/i).first()).toBeVisible();
  await expect(page.getByText(/\$495\.00/i)).toBeVisible();
  await page.getByRole("button", { name: /continue to report/i }).click();
  await expect(page.getByRole("button", { name: /bank credit paper/i })).toBeDisabled();
  await expect(page.locator(".wizard-phase")).toHaveText("Business details");
  await expect(page.getByText(/coming later/i)).toHaveCount(4);
  await expect(page.getByText(/advisor pilot/i)).toHaveCount(0);
  await page.getByRole("button", { name: /valuation advisory/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByText(/some profile data is incomplete/i)).toBeVisible();
  await completeValuationIntake(page);
  const depreciationRatio = page.getByLabel(/depreciation and amortisation \(% of revenue\)/i);
  const operatingNwcRatio = page.getByLabel(/operating working capital \(% of revenue\)/i);
  await expect(depreciationRatio).toHaveAttribute("readonly", "");
  await expect(operatingNwcRatio).toHaveAttribute("readonly", "");
  await page.locator('input[name="depreciation_confirmation"][value="override"]').check();
  await expect(depreciationRatio).not.toHaveAttribute("readonly", "");
  await depreciationRatio.fill("4.2");
  await page.getByLabel(/why are you using this figure/i).first().fill("Updated asset register.");
  await page.getByRole("button", { name: /review and continue/i }).click();
  await expect(page.locator(".wizard-phase")).toHaveText("Review and payment");
  await expect(page.getByRole("heading", { name: /confirm your valuation order/i })).toBeVisible();
  await expect(page.getByText(/inputs are frozen/i)).toBeVisible();
  await expect(page.getByText(/human review/i)).toBeVisible();
  await expect(page.getByText("3 years", { exact: true })).toBeVisible();
  await expect(page.getByText("8.0% each year", { exact: true })).toBeVisible();
  await expect(page.getByText("3.0%", { exact: true })).toBeVisible();
  await expect(page.getByText(/4\.2% of revenue/i)).toBeVisible();
  await expect(page.getByText(/updated by you/i)).toBeVisible();
  await expect(page.getByText(/reason: updated asset register/i)).toBeVisible();
  await expect(page.getByText(/4\.0% of revenue/i)).toBeVisible();
  await expect(page.getByText(/provided by you/i)).toBeVisible();
  await expect(page.getByText(/12\.4% of revenue/i)).toBeVisible();
  await expect(page.getByText(/calculated from the financial statements for 2025/i)).toBeVisible();
  const checkoutResponse = page.waitForResponse((response) =>
    response.url().includes("/wizard/report/checkout") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: /proceed to secure checkout/i }).click();
  await expect((await checkoutResponse).status()).toBe(201);
  await expect(page.getByText(/your report is under review/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".wizard-phase")).toHaveText("Report delivery");
  await expect(page.getByText(/awaiting_review/i)).toHaveCount(0);
  await page.reload();
  await expect(page.getByText(/your report is under review/i)).toBeVisible({ timeout: 15_000 });

  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  await loginOrRegisterAdmin(adminPage);
  await approvePendingReport(adminPage, companyName);
  await adminContext.close();

  await expect(page.getByRole("heading", { name: /your report is ready/i })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("link", { name: /open report/i })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("link", { name: /download pdf/i })).toBeVisible();
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
          details: {
            statement: "bs",
            base_period: "2025",
            balance_sheet_periods: ["2023", "2024"],
            row_key: "cash_and_bank",
          },
        },
      }),
    });
  });
  await page.getByRole("button", { name: /proceed to secure checkout/i }).click();
  await expect(page.getByText(/no payment was taken/i)).toBeVisible();
  await expect(page.locator(".wizard-phase")).toHaveText("Review and payment");
  await expect(page.getByText("Financial statement", { exact: true })).toBeVisible();
  await expect(page.getByText("Balance sheet", { exact: true })).toBeVisible();
  await expect(page.getByText("Selected reporting period", { exact: true })).toBeVisible();
  await expect(page.getByText("Balance sheet periods", { exact: true })).toBeVisible();
  await expect(page.getByText("2025")).toBeVisible();
  await expect(page.getByText("2023, 2024")).toBeVisible();
  await expect(page.getByText(/base_period|balance_sheet_periods|incompatible_balance_sheet_period|row_key|cash_and_bank|\bbs\b/i)).toHaveCount(0);
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
  await page.locator('input[name="depreciation_confirmation"][value="confirm"]').check();
  await page.locator('input[name="operating_nwc_confirmation"][value="confirm"]').check();
  await page.getByLabel(/capital investment \(% of revenue\)/i).fill("4");
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
