import { expect, test } from "@playwright/test";
import path from "node:path";

import {
  completeValuationIntake,
  continueFromUploadWhenReady,
  expectNoHorizontalOverflow,
  loginOrRegisterAdmin,
  register,
  regularEmail,
  submitValuationCheckout,
} from "./helpers";

test("wizard intake and account purchase history are usable on a narrow screen", async ({ page }, testInfo) => {
  if (testInfo.project.name === "chromium") {
    await page.setViewportSize({ width: 320, height: 720 });
  }
  await register(page, regularEmail());
  await expect(page).toHaveURL(/\/wizard$/);
  await expectNoHorizontalOverflow(page);

  await page.getByLabel(/business name/i).fill("Mobile History E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await continueFromUploadWhenReady(page);
  await page.getByRole("button", { name: /valuation advisory/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.locator(".wizard-phase")).toHaveText("Business details");
  await page.getByRole("button", { name: /add normalisation item/i }).click();
  await expectNoHorizontalOverflow(page);
  await completeValuationIntake(page);
  await submitValuationCheckout(page);

  await page.getByRole("link", { name: "Account", exact: true }).click();
  await expect(page.locator(".purchase-record").filter({ hasText: "Mobile History E2E Ltd" })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".purchase-record")).toBeVisible();
  await expect(page.locator(".purchase-table-wrap")).toBeHidden();
  await expectNoHorizontalOverflow(page);
});

test("admin navigation and a representative table stay usable on a narrow screen", async ({ page }, testInfo) => {
  if (testInfo.project.name === "chromium") {
    await page.setViewportSize({ width: 320, height: 720 });
  }
  await loginOrRegisterAdmin(page);
  const navigation = page.locator(".admin-links");
  await expect(navigation).toBeVisible();
  await page.getByRole("link", { name: /companies/i }).click();
  await expect(page).toHaveURL(/\/admin\/companies$/);
  await page.getByRole("button", { name: /add company/i }).click();
  await page.getByLabel(/company name/i).fill("Mobile Admin E2E Ltd");
  await page.getByRole("button", { name: /save company/i }).click();
  await expect(page.locator(".table-wrap").first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
