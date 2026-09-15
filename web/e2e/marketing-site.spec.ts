import { expect, test } from "@playwright/test";

import { expectNoHorizontalOverflow } from "./helpers";

test("signed-out visitors land on the home page rather than the offer page", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("heading", { level: 1, name: "Business valuation reports for New Zealand owners" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);

  const primaryCta = page.getByRole("link", { name: "Get a business valuation" }).first();
  await expect(primaryCta).toHaveAttribute("href", "/login?mode=register");

  await expect(page.getByText("Indicative only. Not financial advice.").first()).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
});

test("the main navigation reaches every published page", async ({ page }) => {
  await page.goto("/");

  const nav = page.getByRole("navigation", { name: "Main", exact: true });
  await nav.getByRole("link", { name: "How it works" }).click();
  await expect(page).toHaveURL(/\/how-it-works$/);
  await expect(page.getByRole("heading", { level: 1, name: "How it works" })).toBeVisible();
  await expect(page.getByText("Your last two to three years of annual financial statements")).toBeVisible();
  // YAML turns an unquoted `2026-09-16` into a Date, so this pins the front-matter date normalising.
  await expect(page.getByText("Last reviewed 16 September 2026")).toBeVisible();

  await nav.getByRole("link", { name: "Valuation" }).click();
  await expect(page).toHaveURL(/\/valuation$/);

  await nav.getByRole("link", { name: "Blog" }).click();
  await expect(page).toHaveURL(/\/blog$/);
  await expect(page.getByRole("heading", { level: 1, name: "Blog" })).toBeVisible();

  await page.getByRole("contentinfo").getByRole("link", { name: "For advisors" }).click();
  await expect(page).toHaveURL(/\/for-advisors$/);
  await expect(page.getByRole("heading", { level: 1, name: "For accountants and advisors" })).toBeVisible();
});

test("an unknown page returns a not found response", async ({ page }) => {
  const response = await page.goto("/no-such-page");
  expect(response?.status()).toBe(404);
});

test("robots and sitemap describe the public pages only", async ({ page }) => {
  const robots = await page.request.get("/robots.txt");
  expect(robots.ok()).toBeTruthy();
  const robotsBody = await robots.text();
  expect(robotsBody).toContain("Sitemap:");
  expect(robotsBody).toContain("Disallow: /admin");

  const sitemap = await page.request.get("/sitemap.xml");
  expect(sitemap.ok()).toBeTruthy();
  const sitemapBody = await sitemap.text();
  expect(sitemapBody).toContain("/valuation");
  expect(sitemapBody).toContain("/how-it-works");
  expect(sitemapBody).not.toContain("/wizard");
});

test("the marketing pages stay usable on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 780 });

  for (const path of ["/", "/how-it-works", "/blog"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  }
});
