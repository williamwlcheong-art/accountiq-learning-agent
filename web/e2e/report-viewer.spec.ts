import { expect, test } from "@playwright/test";
import path from "node:path";

import { register, regularEmail } from "./helpers";

test("completed valuation report viewer renders the professional report safely", async ({ page, context }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Viewer E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByLabel(/^purpose/i).selectOption("understand_value");
  await page.getByLabel(/owner or a key person/i).selectOption("shared");
  await page.getByLabel(/largest customer/i).selectOption("10_to_25");
  await page.getByLabel(/predictable is revenue/i).selectOption("mixed");
  await page.getByLabel(/revenue outlook/i).selectOption("not_sure");
  await page.getByRole("button", { name: /review earnings adjustments/i }).click();
  await page.getByRole("button", { name: /research & prepare valuation/i }).click();
  const link = page.getByRole("link", { name: /open report/i });
  await expect(link).toBeVisible({ timeout: 15_000 });

  const viewer = await context.newPage();
  await viewer.goto((await link.getAttribute("href")) ?? "");
  await expect(viewer.locator("script")).toHaveCount(0);
  await expect(viewer.getByRole("heading", { name: /demo indicative valuation report/i })).toBeVisible();
  await expect(viewer.getByText(/valuation snapshot/i)).toBeVisible();
  const reportBasis = viewer.locator(".cover-report-basis");
  await expect(reportBasis.getByText(/report basis/i)).toBeVisible();
  await expect(reportBasis.getByText(/uploaded financials/i)).toBeVisible();
  await expect(reportBasis.getByText(/five private inputs/i)).toBeVisible();
  await expect(reportBasis.getByText(/public-source trail/i)).toBeVisible();
  await expect(reportBasis.getByText(/accountiq model/i)).toBeVisible();
  const coverBrief = viewer.locator(".cover-brief");
  await expect(coverBrief.getByText(/prepared for/i)).toBeVisible();
  await expect(coverBrief.getByText("Viewer E2E Ltd")).toBeVisible();
  await expect(coverBrief.getByText(/prepared by/i)).toBeVisible();
  await expect(coverBrief.getByText("AccountIQ")).toBeVisible();
  await expect(coverBrief.getByText(/basis of value/i)).toBeVisible();
  await expect(coverBrief.getByText(/demo data only - not for reliance/i)).toBeVisible();
  await expect(viewer.getByRole("heading", { name: /basis of preparation/i })).toBeVisible();
  await expect(viewer.getByText(/questions intentionally not asked/i)).toBeVisible();
  await expect(viewer.getByRole("cell", { name: "Management-confirmed private input" }).first()).toBeVisible();
  await expect(viewer.getByRole("link", { name: /download pdf/i })).toBeVisible();
  await expect(viewer.getByText(/pdf download ready/i)).toBeVisible();
  await expect(viewer.getByText(/professional pdf export is ready/i)).toHaveCount(0);
});
