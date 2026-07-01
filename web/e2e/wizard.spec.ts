import { expect, test } from "@playwright/test";
import path from "node:path";

import { register, regularEmail } from "./helpers";

test("regular user uploads, selects report type, generates report, and opens viewer", async ({ page }) => {
  await register(page, regularEmail());
  await expect(page.getByText("Click or drag file here")).toBeVisible();
  await expect(page.getByText(/last 2-3 years preferred/i)).toBeVisible();
  await page.getByLabel(/business name/i).fill("E2E Holdings Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await expect(page.getByText(/sample\.pdf/i)).toBeVisible();
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByText("Bank Credit Paper").click();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByText(/some profile data is incomplete/i)).toBeVisible();
  await page.getByLabel(/facility type/i).fill("Term loan");
  await page.getByLabel(/amount requested/i).fill("250000");
  await page.getByLabel(/proposed term/i).fill("5");
  await page.getByLabel(/repayment structure/i).fill("Monthly principal and interest");
  await page.getByLabel(/security/i).fill("General security agreement");
  await page.getByLabel(/loan purpose/i).fill("Working capital and expansion");
  await page.getByRole("button", { name: /generate report/i }).click();
  await expect(page.getByText(/status:/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /open report/i })).toBeVisible({ timeout: 15_000 });
});
