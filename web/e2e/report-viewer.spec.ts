import { expect, test } from "@playwright/test";
import path from "node:path";

import { register, regularEmail } from "./helpers";

test("completed report viewer escapes script payloads", async ({ page, context }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Viewer E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByText("Bank Credit Paper").click();
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByLabel(/facility type/i).fill("Term loan");
  await page.getByLabel(/amount requested/i).fill("100000");
  await page.getByLabel(/proposed term/i).fill("3");
  await page.getByLabel(/repayment structure/i).fill("Monthly");
  await page.getByLabel(/security/i).fill("GSA");
  await page.getByLabel(/loan purpose/i).fill("Expansion");
  await page.getByRole("button", { name: /generate report/i }).click();
  const link = page.getByRole("link", { name: /open report/i });
  await expect(link).toBeVisible({ timeout: 15_000 });

  const viewer = await context.newPage();
  await viewer.goto((await link.getAttribute("href")) ?? "");
  await expect(viewer.locator("script")).toHaveCount(0);
  await expect(viewer.getByText("<script>escaped text</script>")).toBeVisible();
});
