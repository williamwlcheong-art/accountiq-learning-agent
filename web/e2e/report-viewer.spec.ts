import { expect, test } from "@playwright/test";
import path from "node:path";

import { approvePendingReport, completeValuationIntake, continueFromUploadWhenReady, loginOrRegisterAdmin, register, regularEmail, submitValuationCheckout } from "./helpers";

test("completed report viewer escapes script payloads", async ({ page, context, browser }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Viewer E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await continueFromUploadWhenReady(page);
  await page.getByRole("button", { name: /valuation advisory/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await completeValuationIntake(page);
  await submitValuationCheckout(page);
  await expect(page.getByText(/your report is under review/i)).toBeVisible({ timeout: 15_000 });

  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  await loginOrRegisterAdmin(adminPage);
  await approvePendingReport(adminPage, "Viewer E2E Ltd");
  await adminContext.close();

  const link = page.getByRole("link", { name: /open report/i });
  await expect(link).toBeVisible({ timeout: 15_000 });

  const viewer = await context.newPage();
  await viewer.goto((await link.getAttribute("href")) ?? "");
  await expect(viewer.locator("script")).toHaveCount(0);
  await expect(viewer.locator("body")).toContainText("<script>escaped text</script>");
  const table = viewer.getByRole("table").first();
  await expect(table).toBeVisible();
  await viewer.setViewportSize({ width: 320, height: 720 });
  const tableScrollRegion = viewer.locator(".table-scroll").first();
  await expect(tableScrollRegion).toHaveAttribute("role", "region");
  await expect(tableScrollRegion).toHaveAttribute("aria-label", /table$/i);
  await expect(tableScrollRegion).toBeVisible();
  await tableScrollRegion.focus();
  await expect(tableScrollRegion).toBeFocused();
  const scrollMetrics = await tableScrollRegion.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollLeft: element.scrollLeft,
    scrollWidth: element.scrollWidth,
  }));
  expect(scrollMetrics.scrollWidth).toBeGreaterThan(scrollMetrics.clientWidth);
  await tableScrollRegion.press("ArrowRight");
  await expect.poll(() => tableScrollRegion.evaluate((element) => element.scrollLeft)).toBeGreaterThan(scrollMetrics.scrollLeft);
  const reportFitsViewport = await viewer.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(reportFitsViewport).toBe(true);
});
