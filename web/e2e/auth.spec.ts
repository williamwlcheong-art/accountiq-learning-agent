import { expect, test } from "@playwright/test";

import { login, register, regularEmail } from "./helpers";

test("unauthenticated root redirects to login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("AccountIQ")).toBeVisible();
});

test("regular user registers, lands on wizard, logs out, and can log in again", async ({ page }) => {
  const email = regularEmail();
  await register(page, email);
  await expect(page).toHaveURL(/\/wizard$/);
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page, email);
  await expect(page).toHaveURL(/\/wizard$/);
});

test("short password is rejected in the browser", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: /^create account$/i }).click();
  await page.getByLabel(/email address/i).fill(regularEmail());
  await page.getByLabel(/^password$/i).fill("short");
  await page.getByLabel(/confirm password/i).fill("short");
  await page.getByRole("button", { name: /^create account$/i }).click();
  await expect(page.locator(".alert-error")).toContainText("at least 8");
});
