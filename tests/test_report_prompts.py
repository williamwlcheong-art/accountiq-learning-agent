"""Unit tests for build_prompt() valuation_advisory branch (Phase 05.1)."""
import copy
import json
import sys
from pathlib import Path
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from report_prompts import (
    build_prompt,
    compute_bank_credit_figures,
    TABLE_SECTIONS_BANK_CREDIT,
    TABLE_SECTIONS_VALUATION,
    SECTION_SCHEMAS,
    VALUATION_REQUIRED_SUBTABLE_SCHEDULE_KEYS,
    VALUATION_TABLE_SCHEDULE_KEYS,
)


def _sample_valuation_result():
    return {
        "research_brief": {
            "company_summary": "Acme Ltd is a NZ digital agency...",
            "sector_summary": "The NZ agency sector...",
            "comparable_transactions": "Recent NZ deals: ...",
            "risk_free_rate": 4.65, "erp": 5.94, "industry_beta": 1.08,
            "industry_category": "Software (System & Application)",
            "inflation_rate": 2.5,
            "sources": ["https://rbnz.govt.nz/...", "https://pages.stern.nyu.edu/~adamodar/.../totalbeta.html"],
        },
        "wacc_scenarios_pct": {"high": 13.5, "mid": 11.07, "low": 8.7},
        "dcf_scenarios": {
            "high": {"enterprise_value_dcf": 4000000},
            "mid": {"enterprise_value_dcf": 5000000},
            "low": {"enterprise_value_dcf": 6500000},
        },
        "illiquidity_discount": {"rate": 0.12, "ev_adjusted": {"high": 3520000, "mid": 4400000, "low": 5720000}},
        "normalised_ebitda": 850000,
        "revenues": 5200000,
        "gross_debt": 350000,
        "net_debt": 200000,
        "cash": 150000,
        "surplus_assets": 50000,
        "forecast_years": 5,
        "revenue_growth_pct": 8.0,
        "growth_assumption_source": "management_outlook_modest_growth",
        "terminal_growth_pct": 2.5,
        "depreciation_base": 120000,
        "maintenance_capex": 120000,
        "operating_working_capital": 260000,
        "working_capital_ratio_pct": 5.0,
        "working_capital_source": "extracted_operating_line_items",
        "executive_summary_table": {
            "headers": ["Indicative valuation", "High valuation", "Midpoint", "Low valuation"],
            "rows": [
                ["Enterprise value", "$3,520,000", "$4,400,000", "$5,720,000"],
                ["Less: net debt", "($200,000)", "($200,000)", "($200,000)"],
                ["Add: surplus assets", "$50,000", "$50,000", "$50,000"],
                ["Indicative equity value", "$3,370,000", "$4,250,000", "$5,570,000"],
            ],
        },
        "wacc_assumptions_table": {
            "headers": ["Component", "High valuation", "Midpoint", "Low valuation"],
            "rows": [
                ["Risk-free rate", "4.7%", "4.7%", "4.7%"],
                ["Equity risk premium", "5.9%", "5.9%", "5.9%"],
                ["Industry beta", "1.08", "1.08", "1.08"],
                ["Private-company WACC", "13.5%", "11.1%", "8.7%"],
                ["Illiquidity discount", "12.0%", "12.0%", "12.0%"],
            ],
        },
        "dcf_analysis_table": {
            "headers": ["DCF item", "High valuation", "Midpoint", "Low valuation"],
            "rows": [
                ["WACC", "13.5%", "11.1%", "8.7%"],
                ["Terminal growth", "2.5%", "2.5%", "2.5%"],
                ["Base revenue", "$5,200,000", "$5,200,000", "$5,200,000"],
                ["Normalised EBITDA", "$850,000", "$850,000", "$850,000"],
                ["Base depreciation", "$120,000", "$120,000", "$120,000"],
                ["Maintenance capex", "$120,000", "$120,000", "$120,000"],
                ["Operating working capital / revenue", "5.0%", "5.0%", "5.0%"],
                ["Enterprise value before illiquidity", "$4,000,000", "$5,000,000", "$6,500,000"],
                ["Illiquidity discount", "12.0%", "12.0%", "12.0%"],
                ["Adjusted enterprise value", "$3,520,000", "$4,400,000", "$5,720,000"],
            ],
        },
        "financial_performance_table": {
            "headers": ["Metric", "2023", "2024", "2025"],
            "rows": [
                ["Revenue", "$980,000", "$1,110,000", "$1,250,000"],
                ["Gross profit", "$588,000", "$682,600", "$787,500"],
                ["EBITDA", "$165,000", "$205,000", "$240,000"],
                ["Net profit after tax", "$105,000", "$128,000", "$150,000"],
            ],
        },
        "financial_ratio_table": {
            "headers": ["Ratio", "2023", "2024", "2025"],
            "rows": [
                ["Revenue growth", "Not available", "13.3%", "12.6%"],
                ["Gross margin", "60.0%", "61.5%", "63.0%"],
                ["EBITDA margin", "16.8%", "18.5%", "19.2%"],
                ["Net profit margin", "10.7%", "11.5%", "12.0%"],
            ],
        },
        "balance_sheet_summary_table": {
            "headers": ["Item", "Value", "Source / treatment"],
            "rows": [
                ["Fixed assets (net)", "$185,000", "Uploaded balance sheet where extracted."],
                ["Operating working capital", "$260,000", "Uploaded balance sheet: operating working-capital line items"],
                ["Cash and bank", "$150,000", "Uploaded balance sheet cash balance."],
                ["Interest-bearing debt", "$350,000", "Uploaded balance sheet borrowings where extracted."],
                ["Net debt", "$200,000", "Interest-bearing debt less cash and bank."],
                ["Surplus / non-operating assets", "$50,000", "Management-supplied surplus or non-operating asset amount."],
                ["Midpoint enterprise value", "$4,400,000", "AccountIQ-calculated DCF midpoint after the illiquidity adjustment."],
                ["Less: net debt", "($200,000)", "Enterprise value to equity value bridge."],
                ["Add: surplus assets", "$50,000", "Separately identified assets not required for normal operations."],
                ["Midpoint equity value", "$4,250,000", "Midpoint enterprise value less net debt plus surplus assets."],
            ],
        },
        "valuation_summary_table": {
            "headers": ["Method / scenario", "Scenario / input", "Enterprise value", "Illiquidity-adjusted EV", "Equity value"],
            "rows": [
                ["DCF - high valuation", "13.5% WACC", "$4,000,000", "$3,520,000", "$3,370,000"],
                ["DCF - midpoint", "11.1% WACC", "$5,000,000", "$4,400,000", "$4,250,000"],
                ["DCF - low valuation", "8.7% WACC", "$6,500,000", "$5,720,000", "$5,570,000"],
                ["Multiples - low", "3.50x EBITDA", "$2,975,000", "Not applied", "$2,825,000"],
                ["Multiples - midpoint", "4.75x EBITDA", "$4,037,500", "Not applied", "$3,887,500"],
                ["Multiples - high", "6.00x EBITDA", "$5,100,000", "Not applied", "$4,950,000"],
            ],
        },
        "multiples_crosscheck_table": {
            "headers": ["Input", "Low", "Mid", "High"],
            "rows": [
                ["EV/EBITDA multiple", "3.50x", "4.75x", "6.00x"],
                ["Normalised EBITDA", "$850,000", "$850,000", "$850,000"],
                ["Indicated enterprise value", "$2,975,000", "$4,037,500", "$5,100,000"],
            ],
        },
        "comparable_evidence_table": {
            "headers": ["Evidence / transaction", "Date", "Metric or multiple", "Relevance and limitations", "Source"],
            "rows": [
                [
                    "Recent NZ digital agency M&A evidence",
                    "2024",
                    "6.0x",
                    "Indicative public evidence; comparability depends on scale and terms.",
                    "Damodaran Online - https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                ],
            ],
        },
        "sources_table": {
            "headers": ["Source", "URL", "Supports / used for"],
            "rows": [
                [
                    "Reserve Bank of New Zealand",
                    "https://rbnz.govt.nz/...",
                    "Risk-free-rate and New Zealand macroeconomic context",
                ],
                [
                    "Damodaran Online",
                    "https://pages.stern.nyu.edu/~adamodar/.../totalbeta.html",
                    "Equity risk premium, beta, multiples and private-company valuation inputs",
                ],
            ],
        },
        "assumption_source_trail": {
            "headers": ["Assumption / input", "Value used", "Primary source", "Why it matters"],
            "rows": [
                ["Normalised EBITDA", "$850,000", "Uploaded financial statements plus management-confirmed earnings adjustments", "Earnings base"],
                ["Revenue and earnings growth", "8.0%", "Management outlook: modest growth", "Forecast driver"],
                ["WACC scenarios", "8.7% / 11.1% / 13.5%", "Public research: RBNZ and Damodaran", "Discount rate"],
            ],
        },
        "normalisation_schedule": {
            "headers": ["Label", "Amount ($)", "Rationale"],
            "rows": [
                ["Owner salary", "$50,000", "above market"],
                ["Normalised EBITDA", "$850,000", "Uploaded earnings basis plus the confirmed adjustments above."],
            ],
        },
        "forecast_cash_flow_schedule": {
            "headers": ["Mid-case forecast", "Year 1", "Year 2"],
            "rows": [
                ["Revenue", 5_616_000, 6_065_280],
                ["Free cash flow to firm", 610_000, 658_800],
            ],
        },
        "sensitivity_matrix": {
            "growth_rates_pct": [6.0, 8.0, 10.0],
            "wacc_by_valuation_scenario_pct": {"high": 8.7, "mid": 11.07, "low": 13.5},
            "adjusted_enterprise_value_rows": [
                {"growth_pct": 6.0, "high": 5000000, "mid": 4200000, "low": 3500000},
                {"growth_pct": 8.0, "high": 5720000, "mid": 4400000, "low": 3520000},
                {"growth_pct": 10.0, "high": 6400000, "mid": 4900000, "low": 3900000},
            ],
        },
        "sensitivity_table": {
            "headers": [
                "Growth assumption",
                "High valuation / 8.7% WACC",
                "Mid valuation / 11.1% WACC",
                "Low valuation / 13.5% WACC",
            ],
            "rows": [
                ["6.0%", "$5,000,000", "$4,200,000", "$3,500,000"],
                ["8.0% - base", "$5,720,000", "$4,400,000", "$3,520,000"],
                ["10.0%", "$6,400,000", "$4,900,000", "$3,900,000"],
            ],
        },
        "specific_risk_factors": {
            "headers": ["Specific risk factor", "Management input", "Valuation relevance", "Report treatment"],
            "rows": [
                ["Owner or key-person transition", "Responsibility is shared across leadership and team", "Continuity", "Confirm handover depth"],
                ["Customer concentration", "10% to 25%", "Retention risk", "Review contract terms"],
            ],
        },
        "multiples_result": {
            "multiple_low": 3.5,
            "multiple_mid": 4.75,
            "multiple_high": 6.0,
            "enterprise_value_low": 2975000,
            "enterprise_value_mid": 4037500,
            "enterprise_value_high": 5100000,
            "normalised_ebitda": 850000,
        },
    }


def test_build_prompt_valuation_includes_table_instruction():
    sys_p, usr = build_prompt(
        report_type="valuation_advisory",
        company_name="Acme Ltd", industry="Digital Agency", description="A NZ agency.",
        financial_rows=[],
        intake_answers={
            "normalisations": [{"label": "Owner salary", "amount": 50000, "rationale": "above market"}],
            "company_website": "https://acme.example",
            "public_source_urls": ["https://companies-register.companiesoffice.govt.nz/acme"],
            "valuation_purpose": "sale_or_transaction",
            "company_location": "Auckland, New Zealand",
            "owner_dependency": "shared",
            "customer_concentration": "10_to_25",
            "revenue_quality": "mixed",
            "revenue_outlook": "not_sure",
            "private_context": "A key contract renews next year.",
            "custom_growth_rate": 8.0,
            "rq_revenue_quality": "3",
            "rq_owner_dependency": "2",
            "legacy_free_text": "Please provide more information in a long valuation questionnaire.",
            "revenue_growth_rate": "7.5",
            "revenue_growth_cagr": "99.0",
            "forecast_horizon": "3 years",
            "terminal_growth_rate": "4.5",
            "wacc": "12.0",
        },
        management_team=[], ebitda_adjustments=[],
        valuation_result=_sample_valuation_result(),
    )
    assert (
        "Return a JSON object with exactly these keys (in this order): "
        f"{json.dumps(SECTION_SCHEMAS['valuation_advisory'])}"
    ) in sys_p
    for s in TABLE_SECTIONS_VALUATION:
        assert s in sys_p, f"system prompt missing table section name: {s}"
    assert "table" in sys_p and "narrative" in sys_p
    assert "Acme Ltd" in usr
    assert "Propellerhead and Marina Terrace indicative valuation report standard" in usr
    assert "Propellerhead/Bayleys" not in usr
    assert "Public Research Brief" in usr
    assert "OpenAI-researched" not in usr
    assert "DCF Scenarios" in usr or "dcf_scenarios" in usr
    assert "Owner salary" in usr
    assert '"maintenance_capex": 120000' in usr
    assert '"working_capital_ratio_pct": 5.0' in usr
    assert '"growth_assumption_source": "Management outlook: modest growth"' in usr
    assert '"working_capital_source": "Uploaded balance sheet: operating working-capital line items"' in usr
    assert "AccountIQ-Calculated Executive Valuation Snapshot" in usr
    assert '"executive_summary_table"' in usr
    assert '"Indicative equity value"' in usr
    assert "AccountIQ-Calculated WACC Assumptions Table" in usr
    assert '"wacc_assumptions_table"' in usr
    assert "AccountIQ-Calculated DCF Analysis Table" in usr
    assert '"dcf_analysis_table"' in usr
    assert "AccountIQ-Calculated Financial Performance Table" in usr
    assert "AccountIQ-Calculated Financial Ratio Table" in usr
    assert '"financial_performance_table"' in usr
    assert '"financial_ratio_table"' in usr
    assert "AccountIQ-Calculated Balance Sheet Summary and EV-to-Equity Bridge" in usr
    assert '"balance_sheet_summary_table"' in usr
    assert '"Midpoint equity value"' in usr
    assert "AccountIQ-Calculated Valuation Summary Table" in usr
    assert '"valuation_summary_table"' in usr
    assert '"Multiples - midpoint"' in usr
    assert "AccountIQ-Calculated Multiples Cross-check Table" in usr
    assert '"multiples_crosscheck_table"' in usr
    assert "AccountIQ-Calculated Comparable Evidence Table" in usr
    assert '"comparable_evidence_table"' in usr
    assert "Recent NZ digital agency M&A evidence" in usr
    assert "AccountIQ-Calculated Sources Table" in usr
    assert '"sources_table"' in usr
    assert '"Gross margin"' in usr
    assert '"12.6%"' in usr
    assert '"assumption_source_trail"' in usr
    assert "AccountIQ-Calculated Normalisation Schedule" in usr
    assert '"normalisation_schedule"' in usr
    assert '"Owner salary"' in usr
    assert "management-confirmed earnings adjustments" in usr
    private_intake_block = usr.split(
        "## Management Intake — Private Facts and Judgement\n", 1
    )[1].split("\n\n## Optional Expert Overrides", 1)[0]
    optional_overrides_block = usr.split(
        "## Optional Expert Overrides (collapsed advanced inputs; do not treat as required management questions)\n", 1
    )[1].split("\n\n## Management-Supplied Public Source Hints", 1)[0]
    source_hints_block = usr.split(
        "## Management-Supplied Public Source Hints (corroboration hints, not standalone proof)\n", 1
    )[1].split("\n\n## Earnings Review — Normalisation Schedule", 1)[0]
    normalised_source_hints_block = " ".join(source_hints_block.split())
    assert "- Valuation purpose: Prepare for a sale or transaction" in usr
    assert "- Main location: Auckland, New Zealand" not in private_intake_block
    assert "- Main location: Auckland, New Zealand" in source_hints_block
    assert "- Owner or key-person dependency: Responsibility is shared across leadership and team" in usr
    assert "- Largest-customer concentration: 10% to 25%" in usr
    assert "- Revenue predictability: A mix of recurring and one-off revenue" in usr
    assert "- Revenue outlook: No specific forecast provided; growth derived from uploaded financial history" in usr
    assert "- Other private context: A key contract renews next year." in usr
    assert "Specific supported annual revenue growth" not in private_intake_block
    assert "- Specific supported annual revenue growth: 8.0" in optional_overrides_block
    assert "sale_or_transaction" not in usr
    assert "10_to_25" not in usr
    assert "not_sure" not in usr
    assert "owner_outlook_modest_growth" not in usr
    assert "management_outlook_modest_growth" not in usr
    assert "rq_revenue_quality" not in usr
    assert "rq_owner_dependency" not in usr
    assert "legacy_free_text" not in usr
    assert "legacy" not in usr.lower()
    assert "long valuation questionnaire" not in usr
    assert "revenue growth rate: 7.5" not in usr.lower()
    assert "revenue_growth_cagr" not in usr
    assert "revenue growth cagr: 99.0" not in usr.lower()
    assert "forecast_horizon" not in usr
    assert "forecast horizon: 3 years" not in usr.lower()
    assert "terminal_growth_rate" not in usr
    assert "terminal growth rate: 4.5" not in usr.lower()
    assert '"wacc": "12.0"' not in usr
    assert "extracted_operating_line_items" not in usr
    assert '"forecast_cash_flow_schedule"' in usr
    assert "cash_flow_schedule" in usr
    assert "Mid-case forecast" in usr
    assert '"sensitivity_matrix"' in usr
    assert "AccountIQ-Calculated Sensitivity Analysis Table" in usr
    assert '"sensitivity_table"' in usr
    assert '"8.0% - base"' in usr
    assert '"specific_risk_factors"' in usr
    assert "specific_risk_factors" in usr
    assert "EBIT after tax plus depreciation" in usr
    assert "Management-Supplied Public Source Hints" in usr
    assert "Owner-Supplied Public Source Hints" not in usr
    assert "Owner Judgement" not in usr
    assert "required owner questions" not in usr
    assert "Earnings Review — Normalisation Schedule" in usr
    assert "User Intake — Normalisation Schedule" not in usr
    assert "Official website: https://acme.example" in usr
    assert "https://companies-register.companiesoffice.govt.nz/acme" in usr
    assert "Do not treat them as standalone proof" in normalised_source_hints_block
    assert "Any public fact included in the report must be supported by a source URL retained" in normalised_source_hints_block
    assert "0–1 scale" not in usr
    assert "risk-adjusted" not in usr.lower()
    assert "executive_summary" in sys_p
    assert "sensitivity_and_risks" in sys_p
    assert "completed professional reports" in sys_p
    assert "completed report drafts" not in sys_p
    assert "executive_summary_table verbatim" in usr
    assert "using wacc_assumptions_table verbatim" in usr
    assert "using dcf_analysis_table verbatim" in usr
    assert "financial_ratio_analysis" in sys_p
    assert "using financial_performance_table verbatim" in usr
    assert "using financial_ratio_table verbatim" in usr
    assert "using balance_sheet_summary_table verbatim" in usr
    assert "using valuation_summary_table verbatim" in usr
    assert "using multiples_crosscheck_table verbatim" in usr
    assert "using sensitivity_table verbatim" in usr
    assert "using comparable_evidence_table verbatim" in usr
    assert "using sources_table verbatim" in usr
    assert 'Each row\'s "Supports / used for" text must explain' in usr
    assert 'do not use generic labels such as "website", "source", "online reference"' in usr
    assert 'vague status words such as "covered"' in usr
    assert "comparable_evidence" in sys_p
    assert "general_principles" in sys_p
    assert "glossary" in sys_p
    assert "sources" in sys_p
    assert "readers, management and market participants should think about risk and uncertainty" in usr
    assert "prospective buyer may assess risk" not in usr
    assert "specific to an SME owner" not in usr
    assert "plain-English, management-friendly language" in usr
    assert "owner-friendly language" not in usr
    assert "Python-Built" not in usr
    assert "Python-Computed" not in usr
    assert "Python-computed" not in usr
    assert "Finished-report discipline" in usr
    assert "not a questionnaire or request for more information" in usr
    assert "Do not ask management, the user or client to provide more documents" in usr
    assert "Do not ask the owner, user or client" not in usr
    assert "Do not introduce extra required valuation questions" in usr
    assert "All figures in the structured blocks above are AccountIQ-calculated" in usr


def test_build_prompt_valuation_suppresses_legacy_addbacks_when_wizard_review_present():
    valuation_result = _sample_valuation_result()
    valuation_result["normalisation_schedule"] = {
        "headers": ["Label", "Amount ($)", "Rationale"],
        "rows": [
            [
                "No adjustments confirmed",
                "$0",
                "The earnings review did not identify genuine one-off, owner-specific or non-operating items for this upload.",
            ],
            [
                "Normalised EBITDA",
                "$850,000",
                "Uploaded earnings basis plus the confirmed adjustments above.",
            ],
        ],
    }
    _, usr = build_prompt(
        report_type="valuation_advisory",
        company_name="Acme Ltd", industry="Digital Agency", description="A NZ agency.",
        financial_rows=[],
        intake_answers={
            "normalisations": [],
            "valuation_purpose": "understand_value",
            "owner_dependency": "shared",
            "customer_concentration": "10_to_25",
            "revenue_quality": "mixed",
            "revenue_outlook": "steady",
        },
        management_team=[],
        ebitda_adjustments=[
            {
                "label": "Stale owner salary adjustment",
                "amount": 999999,
                "rationale": "Old company-level adjustment",
            }
        ],
        valuation_result=valuation_result,
    )

    assert "earnings-review schedule below is authoritative" in usr
    assert "No normalisation items provided." in usr
    assert "No adjustments confirmed" in usr
    assert "Stale owner salary adjustment" not in usr
    assert "999,999" not in usr
    assert "Old company-level adjustment" not in usr


def test_build_prompt_valuation_requires_valuation_result():
    with pytest.raises(ValueError, match="valuation_result is required"):
        build_prompt(
            report_type="valuation_advisory", company_name="A", industry="", description="",
            financial_rows=[], intake_answers={}, management_team=[], ebitda_adjustments=[],
            valuation_result=None,
        )


def test_compute_bank_credit_figures_includes_balance_sheet_strength_and_debt_capacity():
    figures = compute_bank_credit_figures(
        [
            {"canonical_key": "revenue", "statement": "pnl", "values": {"2024": 900000, "2025": 1000000}},
            {"canonical_key": "ebitda", "statement": "pnl", "values": {"2024": 180000, "2025": 240000}},
            {"canonical_key": "net_profit", "statement": "pnl", "values": {"2024": 110000, "2025": 150000}},
            {"canonical_key": "cash_and_bank", "statement": "bs", "values": {"2025": 95000}},
            {"canonical_key": "trade_debtors", "statement": "bs", "values": {"2025": 210000}},
            {"canonical_key": "inventory", "statement": "bs", "values": {"2025": 65000}},
            {"canonical_key": "total_current_assets", "statement": "bs", "values": {"2025": 370000}},
            {"canonical_key": "fixed_assets_net", "statement": "bs", "values": {"2025": 185000}},
            {"canonical_key": "trade_creditors", "statement": "bs", "values": {"2025": 155000}},
            {"canonical_key": "other_current_liab", "statement": "bs", "values": {"2025": 45000}},
            {"canonical_key": "short_term_debt", "statement": "bs", "values": {"2025": 60000}},
            {"canonical_key": "total_current_liab", "statement": "bs", "values": {"2025": 260000}},
            {"canonical_key": "long_term_debt", "statement": "bs", "values": {"2025": 100000}},
            {"canonical_key": "shareholders_equity", "statement": "bs", "values": {"2025": 430000}},
        ],
        {
            "loan_purpose": "Fleet expansion",
            "amount_requested": 250000,
            "proposed_term_years": 5,
            "conservative_funding_cost_pct": 8.5,
            "lvr_percent": 60,
            "security_package": "fleet_and_property",
            "security_value": 450000,
            "repayment_profile": "principal_and_interest",
        },
    )

    assert figures["requested_facility_summary"]["amount_requested"] == "$250,000"
    assert figures["requested_facility_summary"]["calculated_lvr"] == "55.6%"
    assert figures["balance_sheet_strength"]["accounts_receivable"] == "$210,000"
    assert figures["balance_sheet_strength"]["stock_inventory"] == "$65,000"
    assert figures["balance_sheet_strength"]["fixed_assets"] == "$185,000"
    assert figures["balance_sheet_strength"]["ntoa"] == "$260,000"
    constraints = {row["constraint"]: row for row in figures["debt_capacity_table"]}
    assert constraints["Collateral / LVR limit"]["supportable_debt"] == "$270,000"
    assert constraints["Balance-sheet / NTOA support"]["supportable_debt"] == "$195,000"
    assert figures["binding_constraint"] == "Balance-sheet / NTOA support"
    assert figures["facility_terms_table"]["rows"]
    assert figures["sources_and_uses_table"]["headers"] == [
        "Uses",
        "Amount",
        "Sources",
        "Amount",
        "Credit comment",
    ]
    assert figures["security_analysis_table"]["rows"]
    assert figures["credit_metrics_table"]["rows"]
    assert figures["financial_trend_table"]["rows"][-1][0] == "2025"
    assert figures["amortisation_profile_table"]["rows"][0][0] == "Year 1"
    assert figures["proposed_covenants_table"]["rows"]
    assert figures["key_risks_mitigants_table"]["rows"]
    assert figures["conditions_precedent_table"]["rows"]


def test_compute_bank_credit_figures_keeps_missing_balance_sheet_values_unavailable():
    figures = compute_bank_credit_figures(
        [
            {"canonical_key": "revenue", "statement": "pnl", "values": {"2025": 1_000_000}},
            {"canonical_key": "ebitda", "statement": "pnl", "values": {"2025": 240_000}},
            {"canonical_key": "net_profit", "statement": "pnl", "values": {"2025": 150_000}},
        ],
        {
            "loan_purpose": "Refinance existing debt",
            "amount_requested": 250_000,
            "proposed_term_years": 5,
            "conservative_funding_cost_pct": 8.5,
            "lvr_percent": 60,
            "security_package": "general_security",
            "repayment_profile": "principal_and_interest",
        },
    )

    strength = figures["balance_sheet_strength"]
    assert strength["cash"] == "Not available"
    assert strength["accounts_receivable"] == "Not available"
    assert strength["ntoa"] == "Not available"
    assert strength["net_debt"] == "Not available"

    constraints = {row["constraint"]: row for row in figures["debt_capacity_table"]}
    assert constraints["Collateral / LVR limit"]["supportable_debt"] == "Not available"
    assert constraints["Balance-sheet / NTOA support"]["supportable_debt"] == "Not available"
    assert figures["requested_facility_summary"]["binding_constraint"] in {
        "Leverage limit",
        "Interest-cover limit",
        "DSCR / debt-service limit",
    }

    balance_values = " ".join(row[1] for row in figures["balance_sheet_strength_table"]["rows"])
    assert "$0" not in balance_values


def test_compute_bank_credit_figures_respects_selected_covenant_package():
    figures = compute_bank_credit_figures(
        [
            {"canonical_key": "revenue", "statement": "pnl", "values": {"2025": 1000000}},
            {"canonical_key": "ebitda", "statement": "pnl", "values": {"2025": 240000}},
            {"canonical_key": "net_profit", "statement": "pnl", "values": {"2025": 150000}},
        ],
        {
            "loan_purpose": "Fleet expansion",
            "amount_requested": 250000,
            "proposed_term_years": 5,
            "conservative_funding_cost_pct": 8.5,
            "lvr_percent": 60,
            "security_package": "fleet_and_property",
            "repayment_profile": "principal_and_interest",
            "covenant_package_level": "light_touch",
            "selected_covenants": ["min_dscr", "information_reporting"],
            "covenant_package_notes": "Keep the package light while collateral support is confirmed.",
        },
    )

    covenant_rows = figures["proposed_covenants_table"]["rows"]
    assert [row[0] for row in covenant_rows] == ["Minimum DSCR", "Information reporting"]
    assert "Minimum interest cover" not in {row[0] for row in covenant_rows}
    assert figures["covenant_package"]["label"] == "Light touch"
    assert figures["covenant_package"]["selected_labels"] == ["Minimum DSCR", "Information reporting"]
    assert "Keep the package light" in figures["covenant_package"]["notes"]


def test_compute_bank_credit_figures_more_control_package_adds_covenants():
    base_answers = {
        "loan_purpose": "Acquisition funding",
        "amount_requested": 250000,
        "proposed_term_years": 5,
        "conservative_funding_cost_pct": 8.5,
        "lvr_percent": 60,
        "security_package": "fleet_and_property",
        "repayment_profile": "principal_and_interest",
    }
    financial_rows = [
        {"canonical_key": "revenue", "statement": "pnl", "values": {"2025": 1000000}},
        {"canonical_key": "ebitda", "statement": "pnl", "values": {"2025": 240000}},
        {"canonical_key": "net_profit", "statement": "pnl", "values": {"2025": 150000}},
    ]
    balanced = compute_bank_credit_figures(financial_rows, base_answers)
    more_control = compute_bank_credit_figures(
        financial_rows,
        {**base_answers, "covenant_package_level": "more_control"},
    )

    balanced_labels = {row[0] for row in balanced["proposed_covenants_table"]["rows"]}
    stronger_labels = {row[0] for row in more_control["proposed_covenants_table"]["rows"]}
    assert len(stronger_labels) > len(balanced_labels)
    assert "Minimum liquidity" in stronger_labels
    assert "No additional debt" in stronger_labels
    assert more_control["covenant_package"]["label"] == "More protective"


def test_build_prompt_bank_credit_uses_table_backed_credit_paper_contract():
    figures = compute_bank_credit_figures(
        [
            {"canonical_key": "revenue", "statement": "pnl", "values": {"2024": 900000, "2025": 1000000}},
            {"canonical_key": "ebitda", "statement": "pnl", "values": {"2024": 180000, "2025": 240000}},
            {"canonical_key": "net_profit", "statement": "pnl", "values": {"2024": 110000, "2025": 150000}},
        ],
        {
            "loan_purpose": "Acquisition funding",
            "amount_requested": 250000,
            "proposed_term_years": 5,
            "conservative_funding_cost_pct": 8.5,
            "lvr_percent": 60,
            "security_package": "fleet_and_property",
            "repayment_profile": "principal_and_interest",
            "transaction_value": 500000,
            "equity_contribution": 250000,
        },
    )

    system_prompt, user_message = build_prompt(
        report_type="bank_credit_paper",
        company_name="Towing Example Ltd",
        industry="Towing",
        description="A towing and recovery operator.",
        financial_rows=[],
        intake_answers={
            "loan_purpose": "Acquisition funding",
            "amount_requested": 250000,
            "proposed_term_years": 5,
            "conservative_funding_cost_pct": 8.5,
            "lvr_percent": 60,
            "security_package": "fleet_and_property",
            "repayment_profile": "principal_and_interest",
        },
        management_team=[],
        ebitda_adjustments=[],
        bank_credit_figures=figures,
        credit_research_brief={"company_summary": "Public profile summary."},
    )

    assert json.dumps(TABLE_SECTIONS_BANK_CREDIT) in system_prompt
    assert "amortisation_profile_table" in system_prompt
    assert "debt_capacity_table" in system_prompt
    assert "Financial trend table" in user_message
    assert "Sources and uses table" in user_message
    assert "Facility terms table" in user_message
    assert "Security and LVR table" in user_message
    assert "Selected covenant package" in user_message
    assert "Proposed covenants table" in user_message
    assert "write as a completed lender credit paper" in user_message.lower()


def test_build_prompt_other_report_types_unchanged_format():
    with pytest.raises(ValueError, match="bank_credit_figures is required"):
        build_prompt(
            report_type="bank_credit_paper", company_name="A", industry="", description="",
            financial_rows=[], intake_answers={}, management_team=[], ebitda_adjustments=[],
            bank_credit_figures=None,
        )
    sys_p, _ = build_prompt(
        report_type="financial_forecast", company_name="A", industry="", description="",
        financial_rows=[],
        intake_answers={"forecast_horizon": "3 years", "revenue_growth_rate": 0.05},
        management_team=[], ebitda_adjustments=[],
    )
    assert "non-empty string" in sys_p
    assert "financial_performance" not in sys_p


def test_table_sections_cover_all_quantitative_valuation_schedules():
    assert len(TABLE_SECTIONS_VALUATION) == 14
    assert set(TABLE_SECTIONS_VALUATION).issubset(set(SECTION_SCHEMAS["valuation_advisory"]))
    assert "sources" in TABLE_SECTIONS_VALUATION
    assert set(VALUATION_TABLE_SCHEDULE_KEYS) == (
        set(TABLE_SECTIONS_VALUATION) - {"market_position"}
    )
    assert VALUATION_REQUIRED_SUBTABLE_SCHEDULE_KEYS == {
        "dcf_analysis.cash_flow_schedule": "forecast_cash_flow_schedule",
        "sensitivity_and_risks.specific_risk_factors": "specific_risk_factors",
    }


def test_build_prompt_valuation_requires_python_built_table_schedules():
    valuation_result = copy.deepcopy(_sample_valuation_result())
    del valuation_result["valuation_summary_table"]

    with pytest.raises(ValueError, match="valuation_summary->valuation_summary_table"):
        build_prompt(
            report_type="valuation_advisory",
            company_name="Acme Ltd",
            industry="Digital Agency",
            description="A NZ agency.",
            financial_rows=[],
            intake_answers={
                "normalisations": [],
                "valuation_purpose": "understand_value",
                "owner_dependency": "shared",
                "customer_concentration": "10_to_25",
                "revenue_quality": "mixed",
                "revenue_outlook": "steady",
            },
            management_team=[],
            ebitda_adjustments=[],
            valuation_result=valuation_result,
        )
