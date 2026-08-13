import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

import { register, regularEmail } from "./helpers";

async function reachValuationReview(page: Page, businessName: string) {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill(businessName);
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByRole("heading", { name: /choose your report/i })).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: /valuation advisory/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByLabel(/^purpose/i).selectOption("understand_value");
  await page.getByLabel(/owner or a key person/i).selectOption("shared");
  await page.getByLabel(/largest customer/i).selectOption("10_to_25");
  await page.getByLabel(/predictable is revenue/i).selectOption("mixed");
  await page.getByLabel(/revenue outlook/i).selectOption("not_sure");
  await page.getByRole("button", { name: /review earnings adjustments/i }).click();
  await expect(page.getByRole("heading", { name: /your five valuation answers/i })).toBeVisible();
}

test("regular user uploads and sees valuation and credit-paper self-serve picker", async ({ page }) => {
  await page.route("**/api/backend/wizard/document/*/status", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.continue();
  });
  await register(page, regularEmail());
  await expect(page.getByText("Click or drag financial files here")).toBeVisible();
  await expect(page.getByText(/best files for valuation or credit paper/i)).toBeVisible();
  await expect(page.getByText(/accountiq reads the numbers first/i)).toBeVisible();
  await expect(page.getByText(/profit and loss or income statement with revenue and profit\/ebitda/i)).toBeVisible();
  await expect(page.getByText(/balance sheet with cash, borrowings and working-capital balances/i)).toBeVisible();
  await expect(page.getByText(/last 3-4 years are split across separate files/i)).toBeVisible();
  await page.getByLabel(/business name/i).fill("E2E Holdings Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await expect(page.getByText(/sample\.pdf/i)).toBeVisible();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByRole("heading", { name: /reading your financial statements/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /choose your report/i })).toBeVisible();
  await expect(page.getByText(/bank credit paper adds public client research/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /valuation advisory/i })).toBeEnabled();
  await expect(page.getByRole("button", { name: /valuation advisory/i })).toHaveClass(/selected/);
  await expect(
    page.getByRole("button", { name: /valuation advisory/i }).getByText(/core financial information is ready/i),
  ).toBeVisible();
  await expect(page.getByText(/cash-flow analysis and market multiples/i)).toBeVisible();
  await expect(page.getByText(/using DCF/i)).toHaveCount(0);
  await expect(page.getByRole("button", { name: /bank credit paper/i })).toBeEnabled();
  await expect(page.getByRole("button", { name: /financial forecast/i })).toBeDisabled();
  await expect(page.getByText(/coming soon/i)).toHaveCount(3);
  await expect(page.getByText(/still on the roadmap/i)).toHaveCount(3);
  await expect(page.getByLabel(/facility type/i)).toHaveCount(0);
  await expect(page.getByLabel(/forecast horizon/i)).toHaveCount(0);
  await expect(page.getByLabel(/amount to raise/i)).toHaveCount(0);
  await expect(page.getByLabel(/sale rationale/i)).toHaveCount(0);
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByText("Five quick answers", { exact: true })).toBeVisible();
});

test("regular user can upload a multi-file financial pack before choosing a report", async ({ page }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Multi-file E2E Ltd");
  const samplePdf = fs.readFileSync(path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.setInputFiles('input[type="file"]', [
    { name: "profit-and-loss-fy25.pdf", mimeType: "application/pdf", buffer: samplePdf },
    { name: "balance-sheet-fy25.pdf", mimeType: "application/pdf", buffer: samplePdf },
  ]);

  await expect(page.getByText("2 financial statements selected")).toBeVisible();
  await expect(page.getByText("profit-and-loss-fy25.pdf")).toBeVisible();
  await expect(page.getByText("balance-sheet-fy25.pdf")).toBeVisible();
  await page.getByRole("button", { name: /continue/i }).click();

  await expect(page.getByRole("heading", { name: /choose your report/i })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/accountiq has classified the uploaded balance sheet/i)).toBeVisible();
});

test("conflicting duplicate-year figures require a source choice before report selection", async ({ page }) => {
  await page.route("**/api/backend/wizard/financial-review", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "needs_review",
        document_ids: [1, 2],
        unresolved_conflict_ids: ["pnl:revenue:FY2025"],
        invalid_override_ids: [],
        warnings: [],
        conflicts: [
          {
            id: "pnl:revenue:FY2025",
            statement: "pnl",
            row_key: "revenue",
            row_label: "Revenue",
            period: "FY2025",
            suggested_document_id: 1,
            selected_document_id: 1,
            resolved: false,
            sources: [
              { document_id: 1, filename: "draft-fy25.pdf", value: 1250000, currency: "NZD", confidence: 0.95 },
              { document_id: 2, filename: "final-fy25.pdf", value: 1100000, currency: "NZD", confidence: 0.9 },
            ],
          },
        ],
        balance_sheet: { ready: true, warnings: [], issues: [], periods: [] },
      }),
    });
  });
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Conflicting sources E2E Ltd");
  const samplePdf = fs.readFileSync(path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.setInputFiles('input[type="file"]', [
    { name: "draft-fy25.pdf", mimeType: "application/pdf", buffer: samplePdf },
    { name: "final-fy25.pdf", mimeType: "application/pdf", buffer: samplePdf },
  ]);
  await page.getByRole("button", { name: /continue/i }).click();

  await expect(page.getByRole("heading", { name: /choose the source for overlapping figures/i })).toBeVisible({
    timeout: 15_000,
  });
  const sourceSelector = page.getByLabel(/choose a source for revenue in fy2025/i);
  await expect(sourceSelector).toHaveValue("1");
  await sourceSelector.selectOption("2");
  await page.getByRole("button", { name: /continue with selected figures/i }).click();
  await expect(page.getByRole("heading", { name: /choose your report/i })).toBeVisible();
});

test("regular user can complete bank credit paper intake", async ({ page }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Credit E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByRole("heading", { name: /choose your report/i })).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: /bank credit paper/i }).click();
  await expect(page.getByText(/the uploaded financials can support this report/i)).toBeVisible();
  await expect(page.getByText(/debt schedule, payout letters and lender statements/i)).toBeVisible();
  await page.getByRole("button", { name: /continue/i }).click();

  await expect(page.getByRole("heading", { name: /prepare a first-pass credit paper/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /add supporting files/i })).toBeVisible();
  await page.getByRole("button", { name: /add supporting files/i }).click();
  await expect(page.getByRole("heading", { name: /upload your financial statements/i })).toBeVisible();
  await expect(page.getByText(/add lender evidence before preparing the paper/i)).toBeVisible();
  await expect(page.getByText(/debt schedule, payout letters and lender statements/i)).toBeVisible();
  await expect(page.getByLabel(/business name/i)).toHaveValue("Credit E2E Ltd");
  const supportingPdf = fs.readFileSync(path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.setInputFiles('input[type="file"]', {
    name: "credit-supporting.pdf",
    mimeType: "application/pdf",
    buffer: supportingPdf,
  });
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByRole("heading", { name: /choose your report/i })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("button", { name: /bank credit paper/i })).toHaveClass(/selected/);
  await page.getByRole("button", { name: /continue/i }).click();

  await expect(page.getByText("Client research setup", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /accountiq will research the client before drafting/i })).toBeVisible();
  await expect(page.getByText(/collect public company context from the website and links you approve/i)).toBeVisible();
  await page.getByLabel(/business website/i).fill("credit-e2e.example.co.nz");
  await page.getByLabel(/main location/i).fill("Auckland");
  await page.getByLabel(/borrower \/ ownership structure/i).fill("Operating company borrower with owner support");
  await page.getByLabel(/helpful public links/i).fill("https://credit-e2e.example.co.nz/about");
  await page.getByRole("button", { name: /continue to lending questions/i }).click();

  await expect(page.getByText("Facility and security questions", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /only the credit-structuring facts are required/i })).toBeVisible();
  await expect(page.getByText(/client research hints retained/i)).toBeVisible();
  await expect(page.getByText("https://credit-e2e.example.co.nz", { exact: true })).toBeVisible();
  await expect(page.getByText(/optional: add transaction structure, sources & uses or bridge details/i)).toBeVisible();
  await expect(page.getByLabel("Transaction / group structure")).toHaveCount(1);
  await page.getByLabel(/what is the debt for/i).fill("Refinance existing debt and fund fleet expansion.");
  await page.getByLabel(/facility amount requested/i).fill("250000");
  await page.getByLabel(/term of debt/i).fill("5");
  await page.getByLabel(/conservative funding cost/i).fill("8.5");
  await page.getByLabel(/repayment profile/i).selectOption("principal_and_interest");
  await page.getByLabel(/can the debt be secured/i).selectOption("fleet_and_property");
  await page.getByLabel(/lvr \/ advance rate/i).fill("60");
  await page.getByLabel(/estimated security value/i).fill("450000");
  await page.getByLabel(/security notes/i).fill("Fleet list and property valuation to be confirmed before credit committee.");
  await page.getByRole("button", { name: /research & prepare credit paper/i }).click();

  await expect(page.getByRole("link", { name: /open report/i })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: /your bank credit paper is ready/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /screening paper with a clear route to committee/i })).toBeVisible();
  await expect(page.getByText(/coverage, security and debt capacity/i)).toBeVisible();
  await expect(page.getByText(/use this as a screening paper/i)).toBeVisible();
  await expect(page.getByText(/current management accounts, the debt schedule and payout letters/i)).toBeVisible();
  await page.getByRole("button", { name: /add supporting files/i }).click();
  await expect(page.getByRole("heading", { name: /upload your financial statements/i })).toBeVisible();
  await expect(page.getByText(/add lender evidence before preparing the paper/i)).toBeVisible();
});

test("failed financial extraction explains what to upload before valuation questions", async ({ page }) => {
  await page.route("**/api/backend/wizard/document/*/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 123,
        extraction_status: "failed",
        message: "We could not read the uploaded financial statements reliably.",
        demo_mode: false,
      }),
    });
  });

  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Extraction Help Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();

  await expect(page.getByRole("heading", { name: /reading your financial statements/i })).toBeVisible();
  await expect(page.getByText(/no report questions yet/i)).toBeVisible();
  await expect(page.getByText(/usable financial history first/i)).toBeVisible();
  await expect(page.getByText(/profit and loss or income statement/i)).toBeVisible();
  await expect(page.getByText(/balance sheet showing cash, borrowings and working-capital items/i)).toBeVisible();
  await expect(page.getByText(/last 3-4 financial years/i)).toBeVisible();
  await expect(page.getByText("Five quick answers", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: /upload clearer statements/i }).click();
  await expect(page.getByRole("heading", { name: /upload your financial statements/i })).toBeVisible();
});

test("regular user can complete valuation-specific intake", async ({ page, context }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Valuation E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByText("Valuation Advisory").click();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByRole("heading", { name: /valuation can be prepared from this upload/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /add supporting files/i })).toBeVisible();
  await expect(page.getByText(/we will simulate the desk work/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /only five answers are required/i })).toBeVisible();
  await expect(page.getByText(/optional links and private context can be skipped/i)).toBeVisible();
  await expect(page.getByText(/wacc, terminal growth and forecast period/i)).toBeVisible();
  await expect(page.getByText(/private facts only you know/i)).toBeVisible();
  await expect(page.getByText(/0 of 5 required answers complete/i)).toBeVisible();
  await expect(page.getByText(/optional research clues stay optional/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /not sure is an acceptable answer/i })).toBeVisible();
  await expect(page.getByText(/use uploaded financial history or flag the item as a diligence point/i)).toBeVisible();
  await expect(page.getByText(/purpose is the only answer that needs your closest reason/i)).toBeVisible();
  await expect(page.getByText(/sample business research, sample market evidence and simulated valuation assumptions/i)).toBeVisible();
  await expect(page.getByText(/source trail demonstrated/i)).toBeVisible();
  await expect(page.getByText(/sample public evidence and labelled demo urls appear in the finished pack/i)).toBeVisible();
  await expect(page.getByText(/optional: strengthen the report evidence/i)).toBeVisible();
  await expect(page.getByLabel("Forecast / pipeline support")).toHaveCount(1);
  await expect(page.getByText(/valuation inputs/i)).toHaveCount(0);
  await expect(page.getByText(/five required answers, each used in the report/i)).toBeVisible();
  await expect(page.getByText(/we keep this to five required answers/i)).toBeVisible();
  await expect(
    page.getByLabel(/five required answers, each/i).getByText(/owner or key-person dependency/i),
  ).toBeVisible();
  await expect(page.getByText(/operate without the owner/i)).toHaveCount(0);
  await expect(page.getByText(/used to set the report scope/i)).toBeVisible();
  await expect(page.getByText(/continuity, handover and transition risk/i)).toBeVisible();
  await expect(page.getByText(/buyer diligence focus/i)).toHaveCount(0);
  await expect(page.getByText(/buyer confidence/i)).toHaveCount(0);
  await expect(page.getByText(/used to assess concentration risk/i)).toBeVisible();
  await expect(page.getByText(/used to explain cash-flow reliability/i)).toBeVisible();
  await expect(page.getByText(/treat it as a diligence point rather than making you guess/i)).toBeVisible();
  await expect(page.getByText(/uncertainty as a diligence note rather than making you guess/i)).toBeVisible();
  await expect(page.getByText(/instead of forcing a precise answer/i)).toBeVisible();
  await expect(page.getByText(/optional: help us find the right business online/i)).toBeVisible();
  await expect(page.getByLabel(/main location/i)).toBeHidden();
  await expect(page.getByLabel(/helpful public links/i)).toBeHidden();
  await expect(page.getByText(/optional: add private valuation context/i)).toBeVisible();
  await expect(page.getByLabel(/accounts or public research will not show/i)).toBeHidden();
  await expect(
    page.getByRole("heading", { name: /one quick earnings check, then accountiq prepares the report/i }),
  ).toBeVisible();
  await expect(
    page.getByText(/only remaining customer step is to confirm any obvious one-off earnings adjustments/i),
  ).toBeVisible();
  await expect(page.getByText(/accountiq derives wacc, terminal growth, forecast mechanics/i)).toBeVisible();
  await expect(page.getByText(/research, model and report pack/i)).toBeVisible();
  await expect(page.getByText(/business risk assessment/i)).toHaveCount(0);
  await expect(page.getByLabel(/terminal growth rate/i)).toHaveCount(0);
  await page.getByLabel(/^purpose/i).selectOption("understand_value");
  await page.getByLabel(/owner or a key person/i).selectOption("shared");
  await page.getByLabel(/largest customer/i).selectOption("10_to_25");
  await page.getByLabel(/predictable is revenue/i).selectOption("mixed");
  await page.getByLabel(/revenue outlook/i).selectOption("not_sure");
  await expect(page.getByText(/5 of 5 required answers complete/i)).toBeVisible();
  await expect(page.getByText(/derive a conservative assumption from uploaded revenue history/i)).toBeVisible();
  await page.getByText(/optional: help us find the right business online/i).click();
  await expect(page.getByText(/distinguish businesses with similar names/i)).toBeVisible();
  await expect(page.getByText(/we use them as clues, corroborate material public facts/i)).toBeVisible();
  await expect(page.getByText(/supplied links are treated as clues, not standalone proof/i)).toBeVisible();
  await page.getByLabel(/main location/i).fill("  Auckland,   New Zealand  ");
  await page.getByLabel(/helpful public links/i).fill("https://www.linkedin.com/company/valuation-e2e\nnot a useful link");
  await page.getByRole("button", { name: /review earnings adjustments/i }).click();
  await expect(page.getByText(/helpful public link 2 must be a valid website or public url/i)).toBeVisible();
  await expect(page.getByText("Five quick answers", { exact: true })).toBeVisible();
  await page.getByLabel(/helpful public links/i).fill("http://127.0.0.1/internal-source");
  await page.getByRole("button", { name: /review earnings adjustments/i }).click();
  await expect(page.getByText(/helpful public link 1 must be a public website or public url/i)).toBeVisible();
  await expect(page.getByText("Five quick answers", { exact: true })).toBeVisible();
  await page.getByLabel(/helpful public links/i).fill("fc-public.example.co.nz");
  await page.getByRole("button", { name: /review earnings adjustments/i }).click();
  await expect(page.getByRole("heading", { name: /your five valuation answers/i })).toBeVisible();
  await page.getByRole("button", { name: /change answers/i }).click();
  await page.getByText(/optional: help us find the right business online/i).click();
  await page.getByLabel(/helpful public links/i).fill("linkedin.com/company/valuation-e2e");
  await page.getByText(/optional: add private valuation context/i).click();
  await page.getByLabel(/accounts or public research will not show/i).fill("  A key contract\n\nrenews next year.  ");
  await page.getByRole("button", { name: /^back$/i }).click();
  await expect(page.getByText("Valuation Advisory")).toBeVisible();
  await page.getByRole("button", { name: /continue/i }).click();
  await expect(page.getByLabel(/owner or a key person/i)).toHaveValue("shared");
  await expect(page.getByLabel(/revenue outlook/i)).toHaveValue("not_sure");
  await page.getByText(/optional: add private valuation context/i).click();
  await expect(page.getByLabel(/accounts or public research will not show/i)).toHaveValue("A key contract\n\nrenews next year.");
  await page.getByText(/optional: help us find the right business online/i).click();
  await expect(page.getByLabel(/main location/i)).toHaveValue("Auckland, New Zealand");
  await expect(page.getByLabel(/helpful public links/i)).toHaveValue("linkedin.com/company/valuation-e2e");
  await page.getByRole("button", { name: /review earnings adjustments/i }).click();
  await expect(page.getByText(/private facts complete/i)).toBeVisible();
  await expect(page.getByText(/one final check before we prepare the report/i)).toBeVisible();
  await expect(page.getByText(/candidate earnings adjustments already listed for this business/i)).toBeVisible();
  await expect(page.getByText(/found in the financial statements/i)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /your five valuation answers/i })).toBeVisible();
  await expect(page.getByText(/captured from step 1/i)).toBeVisible();
  await expect(page.getByText(/mostly - responsibility is shared/i)).toBeVisible();
  await expect(page.getByText(/10% to 25%/i)).toBeVisible();
  await expect(page.getByText(/not sure - use my financial history/i)).toBeVisible();
  await expect(page.getByText(/research and private context to use/i)).toBeVisible();
  await expect(page.getByText(/optional clues captured/i)).toBeVisible();
  await expect(page.getByText(/auckland, new zealand/i)).toBeVisible();
  await expect(page.getByText(/linkedin\.com\/company\/valuation-e2e/i)).toBeVisible();
  await expect(page.getByText(/a key contract renews next year/i)).toBeVisible();
  await expect(page.getByText(/no more required answers after this check/i)).toBeVisible();
  await expect(page.getByText(/calculation trail/i)).toBeVisible();
  await expect(page.getByText(/research trail/i)).toBeVisible();
  await expect(page.getByText(/source urls retained for review/i)).toBeVisible();
  await expect(page.getByText(/dcf, multiples cross-check, sensitivity analysis and risk factors/i)).toBeVisible();
  await expect(page.getByText(/browser report plus downloadable pdf/i)).toBeVisible();
  await expect(page.getByText(/this is a review, not a finance test/i)).toBeVisible();
  await expect(page.getByText(/remove it, leave it blank or do nothing if you are unsure/i)).toBeVisible();
  await expect(page.getByText(/do not forecast here/i)).toBeVisible();
  await expect(page.getByText(/no extra required answers/i)).toBeVisible();
  await page.getByRole("button", { name: /change answers/i }).click();
  await expect(page.getByLabel(/owner or a key person/i)).toHaveValue("shared");
  await expect(page.getByLabel(/revenue outlook/i)).toHaveValue("not_sure");
  await page.getByRole("button", { name: /review earnings adjustments/i }).click();
  await expect(page.getByRole("heading", { name: /your five valuation answers/i })).toBeVisible();
  await expect(page.getByText(/research and private context to use/i)).toBeVisible();
  await expect(page.getByText(/usually worth adjusting/i)).toBeVisible();
  await expect(page.getByText(/usually leave alone/i)).toBeVisible();
  await expect(page.getByText(/treat any pre-filled items as candidates/i)).toBeVisible();
  await expect(page.getByText(/include a non-zero amount and a short rationale/i)).toBeVisible();
  await expect(page.getByText(/apply to this upload/i)).toBeVisible();
  await expect(page.getByLabel(/owner or a key person/i)).toHaveCount(0);
  await expect(page.getByLabel(/annual replacement manager cost/i)).toBeHidden();
  await expect(page.getByLabel(/interest-bearing debt at valuation date/i)).toBeHidden();
  await expect(page.getByLabel(/specific supported annual revenue growth/i)).toBeHidden();
  await page.getByRole("button", { name: /add an adjustment/i }).click();
  const addedAdjustment = page.locator(".normalisation-row").last();
  await addedAdjustment.getByLabel(/^label$/i).fill("One-off relocation costs");
  await addedAdjustment.getByLabel(/amount/i).fill("12000");
  await addedAdjustment.getByLabel(/rationale/i).fill("Non-recurring relocation setup cost.");
  await page.getByText(/optional: adjust figures we should use/i).click();
  await page.getByLabel(/annual replacement manager cost/i).fill("1000");
  await page.getByLabel(/interest-bearing debt at valuation date/i).fill("2000");
  await page.getByLabel(/surplus or non-operating assets/i).fill("500");
  await page.getByLabel(/specific supported annual revenue growth/i).fill("6.5");
  await page.getByRole("button", { name: /^back$/i }).click();
  await expect(page.getByLabel(/owner or a key person/i)).toHaveValue("shared");
  await expect(page.getByLabel(/revenue outlook/i)).toHaveValue("not_sure");
  await page.getByText(/optional: help us find the right business online/i).click();
  await expect(page.getByLabel(/main location/i)).toHaveValue("Auckland, New Zealand");
  await expect(page.getByLabel(/helpful public links/i)).toHaveValue("https://linkedin.com/company/valuation-e2e");
  await page.getByRole("button", { name: /review earnings adjustments/i }).click();
  const restoredAdjustment = page.locator(".normalisation-row").last();
  await expect(restoredAdjustment.getByLabel(/^label$/i)).toHaveValue("One-off relocation costs");
  await expect(restoredAdjustment.getByLabel(/amount/i)).toHaveValue("12000");
  await expect(restoredAdjustment.getByLabel(/rationale/i)).toHaveValue("Non-recurring relocation setup cost.");
  await page.getByText(/optional: adjust figures we should use/i).click();
  await expect(page.getByLabel(/annual replacement manager cost/i)).toHaveValue("1000");
  await expect(page.getByLabel(/interest-bearing debt at valuation date/i)).toHaveValue("2000");
  await expect(page.getByLabel(/surplus or non-operating assets/i)).toHaveValue("500");
  await expect(page.getByLabel(/specific supported annual revenue growth/i)).toHaveValue("6.5");
  await page.getByLabel(/interest-bearing debt at valuation date/i).fill("-1");
  await page.getByRole("button", { name: /research & prepare valuation/i }).click();
  await expect(page.getByText(/interest-bearing debt at valuation date must be zero or greater/i)).toBeVisible();
  await page.getByLabel(/interest-bearing debt at valuation date/i).fill("2000");
  await page.getByRole("button", { name: /research & prepare valuation/i }).click();
  const openReportLink = page.getByRole("link", { name: /open report/i });
  await expect(openReportLink).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: /your valuation report is ready/i })).toBeVisible();
  await expect(page.getByText(/demo report/i)).toBeVisible();
  await expect(
    page.getByText(/has prepared your labelled demo valuation pack from the uploaded financials, five private answers, earnings review, simulated public research, valuation model and report-letter front matter/i),
  ).toBeVisible();
  await expect(page.getByText(/review it online, download the pdf and use the basis\/source sections/i)).toBeVisible();
  await expect(page.getByText(/when it is ready/i)).toHaveCount(0);
  await expect(page.getByText(/upload and private inputs captured/i)).toBeVisible();
  await expect(page.getByText(/simulated research and market evidence/i)).toBeVisible();
  await expect(page.getByText(/retaining labelled demo source urls for review/i)).toBeVisible();
  await expect(page.getByText(/valuation calculations and quality checks/i)).toBeVisible();
  await expect(page.getByText(/assumption\/source trail/i)).toBeVisible();
  await expect(page.getByText(/report and pdf delivery/i)).toBeVisible();
  await expect(page.getByText(/professional cover, contents, report letter, prepared-by identity, basis of preparation/i)).toBeVisible();
  await expect(page.getByText(/pdf formatting and pdf download/i)).toBeVisible();
  await expect(page.getByText(/no more valuation answers are needed/i)).toBeVisible();
  await expect(page.getByText(/the five private answers and earnings review are saved/i)).toBeVisible();
  await expect(page.getByText(/accountiq derives wacc, terminal growth and forecast mechanics for you/i)).toBeVisible();
  await expect(page.getByText(/report shows the calculation trail, assumptions and labelled demo source urls/i)).toBeVisible();
  await expect(page.getByText(/report pack ready/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /the output is a full valuation pack, not more questions/i })).toBeVisible();
  await expect(page.getByText(/has turned the upload, five private answers and earnings review into the core pages a professional valuation reader expects/i)).toBeVisible();
  await expect(page.getByText(/cover, contents, report letter, prepared-by identity, basis of preparation and reliance limits/i)).toBeVisible();
  await expect(page.getByText(/dcf, wacc, multiples cross-check, equity bridge and sensitivity/i)).toBeVisible();
  await expect(page.getByText(/management input trail, labelled demo source urls, sample comparable evidence and pdf delivery/i)).toBeVisible();
  await expect(page.getByText(/review online first/i)).toBeVisible();
  await expect(page.getByText(/check the valuation snapshot, report letter, basis of preparation and source trail/i)).toBeVisible();
  await expect(page.getByText(/download the pdf for sharing/i)).toBeVisible();
  await expect(page.getByText(/print-ready professional pack for adviser, lender, board or owner discussions/i)).toBeVisible();
  const reportPagePromise = context.waitForEvent("page");
  await openReportLink.click();
  const reportPage = await reportPagePromise;
  await reportPage.waitForLoadState("domcontentloaded");
  await expect(reportPage.getByText(/valuation snapshot/i)).toBeVisible();
  await expect(reportPage.getByRole("heading", { name: /basis of preparation/i })).toBeVisible();
  const basisSection = reportPage.locator("#basis-of-preparation");
  await expect(
    basisSection.getByRole("row", {
      name: /valuation purpose understand what the business may be worth/i,
    }),
  ).toBeVisible();
  await expect(basisSection.getByRole("cell", { name: "Valuation date", exact: true })).toBeVisible();
  await expect(reportPage.getByText(/derived technical assumptions/i)).toBeVisible();
  await expect(reportPage.getByRole("heading", { name: /valuation approach and assumptions/i })).toBeVisible();
  await expect(reportPage.getByText(/assumption \/ input/i)).toBeVisible();
  await expect(reportPage.getByRole("cell", { name: "Management-confirmed private input" }).first()).toBeVisible();
  await expect(reportPage.getByRole("heading", { name: /mid-case forecast cash-flow schedule/i })).toBeVisible();
  await expect(reportPage.getByRole("heading", { name: /specific risk factors/i })).toBeVisible();
  await expect(reportPage.getByRole("cell", { name: "Customer concentration", exact: true })).toBeVisible();
  await expect(reportPage.getByRole("link", { name: /rbnz\.govt\.nz/i }).first()).toBeVisible();
  await expect(reportPage.getByRole("link", { name: /download pdf/i })).toBeVisible();
  await expect(reportPage.getByText(/pdf download ready/i)).toBeVisible();
  await expect(reportPage.getByText(/professional pdf export is ready/i)).toHaveCount(0);
  const pdfLink = page.getByRole("link", { name: /download pdf/i });
  await expect(pdfLink).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await pdfLink.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/AIQ-VAL-\d{6}-demo-indicative-valuation\.pdf$/);
  expect(await download.failure()).toBeNull();
});

test("source-backed valuation ready state uses completion language", async ({ page }) => {
  const reportId = 987655;

  await reachValuationReview(page, "Live Ready Copy Ltd");

  await page.route("**/api/backend/wizard/report/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ report_id: reportId, status: "queued" }),
    });
  });
  await page.route(`**/api/backend/wizard/report/${reportId}/status`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: reportId,
        report_type: "valuation_advisory",
        status: "done",
        error_message: null,
        created_at: "2026-07-04T00:00:00Z",
        completed_at: "2026-07-04T00:01:00Z",
        demo_mode: false,
      }),
    });
  });

  await page.getByRole("button", { name: /research & prepare valuation/i }).click();
  await expect(page.getByRole("heading", { name: /your valuation report is ready/i })).toBeVisible();
  await expect(page.getByText(/has prepared your source-backed valuation pack from the uploaded financials, five private answers, earnings review, market research, valuation model and report-letter front matter/i)).toBeVisible();
  await expect(page.getByText(/review it online, download the pdf and use the basis\/source sections/i)).toBeVisible();
  await expect(page.getByText(/when it is ready/i)).toHaveCount(0);
  await expect(page.getByText(/report pack ready/i)).toBeVisible();
  await expect(page.getByText(/report shows the calculation trail, assumptions and retained source urls/i)).toBeVisible();
  await expect(page.getByText(/management input trail, public source urls, comparable evidence and pdf delivery/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /open report/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /download pdf/i })).toBeVisible();
  await expect(page.getByText(/review online first/i)).toBeVisible();
  await expect(page.getByText(/check the valuation snapshot, report letter, basis of preparation and source trail/i)).toBeVisible();
  await expect(page.getByText(/download the pdf for sharing/i)).toBeVisible();
  await expect(page.getByText(/print-ready professional pack for adviser, lender, board or owner discussions/i)).toBeVisible();
});

test("valuation generation failure reassures the user their answers are saved for retry", async ({ page }) => {
  const reportId = 987654;
  let retryRequests = 0;
  let afterRetry = false;

  await reachValuationReview(page, "Valuation Retry Ltd");

  await page.route("**/api/backend/wizard/report/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ report_id: reportId, status: "queued" }),
    });
  });
  await page.route(`**/api/backend/wizard/report/${reportId}/status`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: reportId,
        report_type: "valuation_advisory",
        status: afterRetry ? "generating" : "failed",
        error_message: "temporary generation failure",
        created_at: "2026-07-04T00:00:00Z",
        completed_at: null,
        demo_mode: false,
      }),
    });
  });
  await page.route(`**/api/backend/wizard/report/${reportId}/retry`, async (route) => {
    retryRequests += 1;
    afterRetry = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: reportId,
        report_type: "valuation_advisory",
        status: "queued",
        error_message: null,
        created_at: "2026-07-04T00:00:00Z",
        completed_at: null,
        demo_mode: false,
      }),
    });
  });

  await page.getByRole("button", { name: /research & prepare valuation/i }).click();
  await expect(page.getByRole("heading", { name: /we paused this valuation report/i })).toBeVisible();
  await expect(page.getByText(/we kept this unfinished report out of delivery/i)).toBeVisible();
  await expect(page.getByText(/your financial upload, five private answers and earnings review are saved/i)).toBeVisible();
  await expect(page.getByText(/you do not need to enter the valuation answers again/i)).toBeVisible();
  await expect(page.getByText(/temporary generation failure/i)).toHaveCount(0);

  await page.getByRole("button", { name: /retry preparation/i }).click();
  await expect.poll(() => retryRequests).toBe(1);
  await expect(page.getByText(/source-backed valuation pack/i)).toBeVisible();
  await expect(
    page.locator(".valuation-prep-step", { hasText: /research and market evidence/i }),
  ).toHaveClass(/valuation-prep-step-complete/);
  await expect(
    page.locator(".valuation-prep-step", { hasText: /valuation calculations and quality checks/i }),
  ).toHaveClass(/valuation-prep-step-current/);
  await expect(page.getByText(/report-letter front matter and pdf formatting/i)).toBeVisible();
  await expect(page.getByText(/pdf formatting and pdf download/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /the output is a full valuation pack, not more questions/i })).toBeVisible();
  await expect(page.getByText(/dcf, wacc, multiples cross-check, equity bridge and sensitivity/i)).toBeVisible();
});
