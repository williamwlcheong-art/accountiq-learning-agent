import { expect, test } from "@playwright/test";

import { login, register, regularEmail } from "./helpers";

test("unauthenticated root shows the marketing home page", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("heading", { level: 1, name: "Business valuation reports for New Zealand owners" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "See what is in the report" })).toHaveAttribute("href", "/valuation");
});

test("regular user registers, lands on their valuations, logs out, and can log in again", async ({ page }) => {
  const email = regularEmail();
  await register(page, email);
  await expect(page).toHaveURL(/\/reports$/);
  await expect(page.getByRole("heading", { level: 1, name: "Your valuations" })).toBeVisible();
  await page.getByRole("button", { name: /account menu/i }).click();
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page, email);
  await expect(page).toHaveURL(/\/reports$/);
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
