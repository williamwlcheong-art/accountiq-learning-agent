import { expect, test } from "@playwright/test";

import { expectNoHorizontalOverflow } from "./helpers";

test("public valuation page explains the bounded early-access offer", async ({ page }) => {
  await page.goto("/valuation");

  await expect(page).toHaveURL(/\/valuation$/);
  await expect(page.getByRole("heading", { level: 1, name: "Know what your business may be worth" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Early-access fixed-fee offer" })).toBeVisible();
  await expect(page.getByText("Your fixed fee is shown before payment.")).toBeVisible();
  await expect(page.getByText("Indicative only. Not financial advice. Reviewed before delivery.").first()).toBeVisible();
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);

  const sectionNavigation = page.getByRole("navigation", { name: "Valuation page sections" });
  await expect(sectionNavigation).toBeVisible();
  await expect(sectionNavigation.getByRole("link", { name: "What you get" })).toHaveAttribute("href", "#inclusions");
  await expect(sectionNavigation.getByRole("link", { name: "How it works" })).toHaveAttribute("href", "#process");
  await expect(sectionNavigation.getByRole("link", { name: "FAQ" })).toHaveAttribute("href", "#faq");

  const headingLevels = await page.getByRole("heading").evaluateAll((headings) =>
    headings.map((heading) => Number(heading.tagName.slice(1))),
  );
  for (let index = 1; index < headingLevels.length; index += 1) {
    expect(headingLevels[index]).toBeLessThanOrEqual(headingLevels[index - 1] + 1);
  }

  const primaryCta = page.getByRole("link", { name: "Get a Business Valuation" }).first();
  await expect(primaryCta).toHaveAttribute("href", "/login");
  await expect(page.getByRole("link", { name: "Sign in" }).first()).toHaveAttribute("href", "/login");

  const externalPaymentLinks = page.locator('a[href*="stripe"], a[href*="checkout"]');
  await expect(externalPaymentLinks).toHaveCount(0);

  const bodyText = (await page.locator("body").textContent()) ?? "";
  expect(bodyText).not.toMatch(/\$495|2,250/);
  expect(bodyText).toMatch(/not financial advice/i);
  expect(bodyText).toMatch(/not a certified, official, or court-standard valuation/i);
  expect(bodyText).toContain("Recent PDF or Excel financial statements covering the last two to three years are preferred.");
  expect(bodyText).toContain("Software prepares the first draft, and a human reviewer checks the report before it is released to your account.");

  // Smoke-check known positive marketing phrases. The explicit negative copy above
  // is the primary contract because a generic blacklist cannot understand negation.
  for (const forbiddenPositiveClaim of [
    /get an instant valuation/i,
    /guaranteed valuation/i,
    /certified valuation service/i,
    /official valuation service/i,
  ]) {
    expect(bodyText).not.toMatch(forbiddenPositiveClaim);
  }
});

test("public valuation page remains usable at 320px", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto("/valuation");

  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const mobileHeader = page.getByRole("banner");
  await expect(mobileHeader.getByRole("link", { name: "Sign in" })).toBeVisible();
  await expect(mobileHeader.getByRole("link", { name: "Get a valuation" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Get a Business Valuation" }).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
