import { expect, test } from "@playwright/test";

import { register, regularEmail } from "./helpers";

test("regular user is redirected away from admin", async ({ page }) => {
  await register(page, regularEmail());
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/wizard$/);
});
