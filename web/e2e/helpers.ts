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

export async function completeValuationIntake(page: Page) {
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
    await page.locator(`label[for="${name}-3"]`).click();
  }
}

export async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
}
