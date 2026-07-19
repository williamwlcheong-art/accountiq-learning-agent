import { expect, Page } from "@playwright/test";

export const regularEmail = () => `regular-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
export const adminEmail = () => "owner-e2e@example.com";
export const password = "correcthorse";

export async function register(page: Page, email: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: /^create account$/i }).click();
  await page.getByLabel(/email address/i).fill(email);
  await page.getByLabel(/^password$/i).fill(password);
  await page.getByLabel(/confirm password/i).fill(password);
  await page.getByRole("button", { name: /^create account$/i }).click();
  await expect(page).toHaveURL(/\/(admin|wizard)$/);
}

export async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel(/email address/i).fill(email);
  await page.getByLabel(/^password$/i).fill(password);
  await page.getByRole("button", { name: /^sign in$/i }).click();
}

export async function loginOrRegisterAdmin(page: Page) {
  await login(page, adminEmail());
  await expect(page).toHaveURL(/\/admin$/);
}

export async function continueFromUploadWhenReady(page: Page) {
  await expect(page.getByText(/ready for valuation intake/i)).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: /continue to report/i }).click();
}

export async function submitValuationCheckout(page: Page) {
  await page.getByRole("button", { name: /review and continue/i }).click();
  await expect(page.getByRole("heading", { name: /confirm your valuation order/i })).toBeVisible();
  await page.getByRole("button", { name: /proceed to secure checkout/i }).click();
}

export async function completeValuationIntake(page: Page) {
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
    await page.locator(`label[for="${name}-3"]`).click();
  }
}

export async function approvePendingReport(page: Page, companyName: string) {
  await page.goto("/admin/reports");
  const row = page.locator("tr").filter({ hasText: companyName });
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(row.getByRole("link", { name: /open draft/i })).toBeVisible();
  await row.getByRole("button", { name: /^approve$/i }).click();
  await expect(page.getByText(/approved and released/i)).toBeVisible();
}

export async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
}
