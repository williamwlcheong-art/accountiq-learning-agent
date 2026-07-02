import { expect, test } from "@playwright/test";
import path from "node:path";

import { completeValuationIntake, register, regularEmail } from "./helpers";

test("completed report viewer escapes script payloads", async ({ page, context }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Viewer E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByRole("button", { name: /valuation advisory/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await completeValuationIntake(page);
  await page.getByRole("button", { name: /generate report/i }).click();
  const link = page.getByRole("link", { name: /open report/i });
  await expect(link).toBeVisible({ timeout: 15_000 });

  const viewer = await context.newPage();
  await viewer.goto((await link.getAttribute("href")) ?? "");
  await expect(viewer.locator("script")).toHaveCount(0);
  await expect(viewer.locator("body")).toContainText("<script>escaped text</script>");
});
