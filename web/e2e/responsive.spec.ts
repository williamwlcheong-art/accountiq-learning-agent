import { expect, test } from "@playwright/test";

import { expectNoHorizontalOverflow, register, regularEmail } from "./helpers";

test("wizard does not horizontally overflow on mobile", async ({ page }) => {
  await register(page, regularEmail());
  await expect(page).toHaveURL(/\/wizard$/);
  await expectNoHorizontalOverflow(page);
});
