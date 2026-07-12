import { expect, test } from "@playwright/test";
import path from "node:path";

import {
  approvePendingReport,
  completeValuationIntake,
  loginOrRegisterAdmin,
  register,
  regularEmail,
} from "./helpers";

test("customer account shows purchase delivery status and released report actions", async ({ page, browser }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("History E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByRole("button", { name: /valuation advisory/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await completeValuationIntake(page);
  await page.getByRole("button", { name: /generate report/i }).click();
  await expect(page.getByText(/your report is under review/i)).toBeVisible({ timeout: 15_000 });

  await page.goto("/account");
  const purchase = page.locator("tr").filter({ hasText: "History E2E Ltd" });
  await expect(purchase).toBeVisible();
  await expect(purchase).toContainText("$495.00");
  await expect(purchase).toContainText("Awaiting review");
  await expect(purchase.getByRole("link", { name: /open report/i })).toHaveCount(0);

  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  await loginOrRegisterAdmin(adminPage);
  await approvePendingReport(adminPage, "History E2E Ltd");
  await adminContext.close();

  await page.reload();
  const releasedPurchase = page.locator("tr").filter({ hasText: "History E2E Ltd" });
  await expect(releasedPurchase).toContainText("Ready");
  await expect(releasedPurchase.getByRole("link", { name: /open report/i })).toBeVisible();
  await expect(releasedPurchase.getByRole("link", { name: /download pdf/i })).toBeVisible();
});
