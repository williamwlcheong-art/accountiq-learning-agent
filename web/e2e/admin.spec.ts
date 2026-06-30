import { expect, test } from "@playwright/test";
import path from "node:path";

import { adminEmail, register } from "./helpers";

test("owner email registers as admin and can use admin workflows", async ({ page }) => {
  await register(page, adminEmail());
  await expect(page).toHaveURL(/\/admin$/);

  await page.getByRole("link", { name: /companies/i }).click();
  await page.getByRole("button", { name: /add company/i }).click();
  await page.getByLabel(/company name/i).fill("Admin E2E Ltd");
  await page.getByLabel(/sector/i).fill("Professional Services");
  await page.getByRole("button", { name: /save company/i }).click();
  await expect(page.getByText("Admin E2E Ltd")).toBeVisible();

  await page.getByRole("link", { name: /^upload$/i }).click();
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /upload/i }).click();
  await expect(page.getByText("done")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: /documents/i }).click();
  await expect(page.getByText("sample.pdf")).toBeVisible();

  await page.getByRole("link", { name: /financials/i }).click();
  await expect(page.getByText(/revenue/i)).toBeVisible({ timeout: 15_000 });
});
