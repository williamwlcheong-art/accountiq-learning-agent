# AccountIQ sector research library

This folder contains version-controlled, New Zealand-focused sector baselines used by
AccountIQ when preparing the market-research sections of a Bank Credit Paper or
Business Valuation Advisory report.

## How the application uses the library

1. `index.json` lists the available sector packs and broad matching aliases.
2. `backend/sector_library.py` matches the company sector and business description to
   one pack and, where possible, one sub-sector.
3. The selected pack is added to the retained research evidence before the report is
   written. This works in OpenAI provider mode and in deterministic evidence mode.
4. The report identifies the selected pack, its review date, relevant source URLs and
   the limitations of using generic sector information.
5. `quarterly/` supplies a separate, versioned macroeconomic and sector-scale layer.
   Its tables and chart series are added deterministically to valuation and credit
   reports in provider, evidence and demo modes.

The initial library covers logistics, construction, retail, hospitality,
manufacturing, professional services, early childhood education and care, and import
distribution.

## Evidence boundary

These packs are generic research baselines. They do not establish facts about the
subject business and must not override uploaded financial statements, management
answers, contracts, customer data, asset appraisals or other borrower-specific
evidence. A report should phrase pack-derived conclusions as typical sector
characteristics to test against the subject business.

The packs do not provide current comparable-company or transaction multiples, a
company-specific beta, a funding rate, an asset valuation or a credit decision. Those
items require current, separately cited evidence. The application uses sector packs to
improve research scope, lender questions, risk analysis and valuation interpretation,
not to manufacture numerical market evidence.

The quarterly layer uses broad official-industry turnover or structural measures. For
private sectors, AccountIQ calls these **sector turnover/scale proxies**, not market
capitalisation. They do not establish subject-company market share or value.

## Maintenance

- Review each pack at least annually and sooner after material regulatory, funding,
  trade, labour-market or industry-structure changes.
- Refresh the versioned numeric layer in `quarterly/` after the principal March, June,
  September and December releases. Create a new snapshot rather than silently changing
  a prior report basis.
- Update `as_of_date`, `next_review_date` and affected source records together.
- Prefer primary sources such as Stats NZ, ministries, regulators and legislation.
- Retain older source dates where the source remains relevant, but do not present an
  old strategy or discontinued programme as current policy.
- Run `python -m pytest tests/test_sector_library.py tests/test_market_intelligence.py -q`
  after changing the library.

## Adding a sector or sub-sector

Copy an existing JSON pack, keep `schema_version` at the current supported version,
use a unique `sector_id`, add at least three meaningful sub-sectors, and register the
file in `index.json`. Aliases should be specific enough to avoid false matches; avoid
single generic words such as `services`, `company` or `business`.
