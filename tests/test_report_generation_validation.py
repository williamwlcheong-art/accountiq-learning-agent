"""Strict validation tests for customer-facing generated reports."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as main_module
from main import (
    _customer_safe_report_failure_message,
    _enforce_valuation_professional_content_audit,
    _e2e_report_content,
    _parse_json_from_response,
    _validate_generated_report_content,
    _validate_valuation_report_figures,
)
from report_prompts import SECTION_SCHEMAS
from report_quality import ReportQualityAudit, ReportQualityIssue


def _sample_valuation_result() -> dict:
    return {
        "wacc_scenarios_pct": {"high": 9.9, "mid": 11.5, "low": 13.4},
        "dcf_scenarios": {
            "high": {"enterprise_value_dcf": 3_209_000},
            "mid": {
                "enterprise_value_dcf": 2_624_000,
                "yearly": [
                    {
                        "year": 1,
                        "revenue": 1_350_000,
                        "ebit": 282_960,
                        "tax": 79_229,
                        "capex": 27_000,
                        "change_nwc": 5_000,
                        "fcff": 198_731,
                        "dcf": 178_234,
                    },
                    {
                        "year": 2,
                        "revenue": 1_458_000,
                        "ebit": 305_597,
                        "tax": 85_567,
                        "capex": 29_160,
                        "change_nwc": 5_400,
                        "fcff": 214_630,
                        "dcf": 172_639,
                    },
                    {
                        "year": 3,
                        "revenue": 1_574_640,
                        "ebit": 330_045,
                        "tax": 92_412,
                        "capex": 31_493,
                        "change_nwc": 5_832,
                        "fcff": 231_800,
                        "dcf": 167_220,
                    },
                    {
                        "year": 4,
                        "revenue": 1_700_611,
                        "ebit": 356_448,
                        "tax": 99_805,
                        "capex": 34_012,
                        "change_nwc": 6_299,
                        "fcff": 250_344,
                        "dcf": 161_971,
                    },
                    {
                        "year": 5,
                        "revenue": 1_836_660,
                        "ebit": 384_964,
                        "tax": 107_790,
                        "capex": 36_733,
                        "change_nwc": 6_802,
                        "fcff": 270_372,
                        "dcf": 156_887,
                    },
                ],
            },
            "low": {"enterprise_value_dcf": 2_152_000},
        },
        "illiquidity_discount": {
            "rate": 0.118,
            "ev_adjusted": {
                "high": 2_831_000,
                "mid": 2_314_000,
                "low": 1_898_000,
            },
        },
        "normalised_ebitda": 287_000,
        "gross_debt": 160_000,
        "cash": 95_000,
        "surplus_assets": 0,
        "multiples_result": {
            "enterprise_value_low": 1_435_000,
            "enterprise_value_mid": 1_722_000,
            "enterprise_value_high": 2_009_000,
        },
        "executive_summary_table": {
            "headers": ["Indicative valuation", "High", "Mid", "Low"],
            "rows": [
                ["Enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
                ["Less: net debt", "$65,000", "$65,000", "$65,000"],
                ["Indicative equity value", "$2,766,000", "$2,249,000", "$1,833,000"],
            ],
        },
        "wacc_assumptions_table": {
            "headers": ["Component", "High valuation", "Mid valuation", "Low valuation"],
            "rows": [
                ["Risk-free rate", "4.4%", "4.4%", "4.4%"],
                ["Equity risk premium", "5.6%", "5.9%", "6.2%"],
                ["Industry total beta", "1.05", "1.20", "1.35"],
                ["WACC", "9.9%", "11.5%", "13.4%"],
                ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
            ],
        },
        "dcf_analysis_table": {
            "headers": ["DCF item", "High valuation", "Mid valuation", "Low valuation"],
            "rows": [
                ["WACC", "9.9%", "11.5%", "13.4%"],
                ["Terminal growth", "2.5%", "2.5%", "2.5%"],
                ["Base revenue", "$1,250,000", "$1,250,000", "$1,250,000"],
                ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
                ["Base depreciation", "$25,000", "$25,000", "$25,000"],
                ["Maintenance capex", "$25,000", "$25,000", "$25,000"],
                ["Operating working capital / revenue", "5.0%", "5.0%", "5.0%"],
                ["Enterprise value before illiquidity", "$3,209,000", "$2,624,000", "$2,152,000"],
                ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
                ["Adjusted enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
            ],
        },
        "forecast_cash_flow_schedule": {
            "headers": ["Mid-case forecast", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
            "rows": [
                ["Revenue", 1_350_000, 1_458_000, 1_574_640, 1_700_611, 1_836_660],
                ["EBITDA", 309_960, 334_757, 361_537, 390_460, 421_697],
                ["EBIT", 282_960, 305_597, 330_045, 356_448, 384_964],
                ["Tax", 79_229, 85_567, 92_412, 99_805, 107_790],
                ["Maintenance capex", 27_000, 29_160, 31_493, 34_012, 36_733],
                ["Change in operating working capital", 5_000, 5_400, 5_832, 6_299, 6_802],
                ["Free cash flow to firm", 198_731, 214_630, 231_800, 250_344, 270_372],
                ["Discounted free cash flow", 178_234, 172_639, 167_220, 161_971, 156_887],
            ],
        },
        "financial_performance_table": {
            "headers": ["Metric", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
            "rows": [
                ["Revenue", "$980,000", "$1,110,000", "$1,250,000", "$1,350,000"],
                ["Less: direct costs / cost of sales", "($392,000)", "($427,400)", "($462,500)", "($499,500)"],
                ["Gross profit", "$588,000", "$682,600", "$787,500", "$850,500"],
                ["Less: operating expenses before EBITDA", "($423,000)", "($477,600)", "($547,500)", "($591,500)"],
                ["Key expense breakdown - wages and salaries", "($240,000)", "($272,000)", "($310,000)", "($335,000)"],
                ["Key expense breakdown - rent and occupancy", "($84,000)", "($90,000)", "($96,000)", "($102,000)"],
                ["Key expense breakdown - advertising and marketing", "($30,000)", "($36,000)", "($42,000)", "($45,000)"],
                ["Key expense breakdown - insurance", "($15,000)", "($16,600)", "($18,000)", "($20,000)"],
                ["Key expense breakdown - other operating expenses", "($54,000)", "($63,000)", "($81,500)", "($89,500)"],
                ["EBITDA", "$165,000", "$205,000", "$240,000", "$259,000"],
                ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                ["Less: depreciation and amortisation", "($20,000)", "($22,000)", "($25,000)", "($27,000)"],
                ["EBIT", "$145,000", "$183,000", "$215,000", "$232,000"],
                ["Net profit after tax", "$105,000", "$128,000", "$150,000", "$163,000"],
            ],
        },
        "financial_ratio_table": {
            "headers": ["Ratio", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
            "rows": [
                ["Revenue growth", "Not available", "13.3%", "12.6%", "8.0%"],
                ["Gross margin", "60.0%", "61.5%", "63.0%", "63.0%"],
                ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                ["Net profit margin", "10.7%", "11.5%", "12.0%", "12.1%"],
            ],
        },
        "balance_sheet_summary_table": {
            "headers": ["Balance sheet item", "Value", "Commentary / treatment"],
            "rows": [
                ["Cash and bank", "$95,000", "Available cash shown separately from operating assets and included in the equity bridge."],
                ["Accounts receivable / trade debtors", "$210,000", "Customer receivables included in operating asset and NTOA context."],
                ["Inventory / stock", "$65,000", "Stock on hand included in operating asset and NTOA context."],
                ["Total current assets", "$370,000", "Uploaded balance sheet current-asset total; supports the working-capital context."],
                ["Operating fixed assets", "$185,000", "Operating asset base shown for context; not used as a standalone asset valuation."],
                ["Other non-current assets", "$295,000", "Other long-term assets shown for balance-sheet completeness."],
                ["Total assets", "$850,000", "Reported asset base shown as financial-position context."],
                ["Accounts payable / trade creditors", "$155,000", "Trade payables included in operating liability and NTOA context."],
                ["Other current liabilities", "$45,000", "Other operating current liabilities included in NTOA context where extracted."],
                ["Short-term loans / current borrowings", "$60,000", "Current interest-bearing borrowings included in the debt bridge."],
                ["Total current liabilities", "$260,000", "Uploaded balance sheet current-liability total; supports the working-capital context."],
                ["Long-term loans / borrowings", "$100,000", "Non-current interest-bearing borrowings included in the debt bridge."],
                ["Other non-current liabilities", "$60,000", "Other long-term liabilities shown for balance-sheet completeness."],
                ["Total liabilities", "$420,000", "Reported liability base shown as solvency and leverage context."],
                ["Shareholders' equity / net assets", "$430,000", "Book equity is shown for context and reconciled separately from going-concern enterprise value."],
                ["Net tangible operating assets (NTOA)", "$260,000", "Receivables, stock and fixed assets less accounts payable and other operating current liabilities, excluding cash and interest-bearing debt."],
                ["Operating working capital", "$75,000", "Accounts receivable and stock less accounts payable and other operating current liabilities."],
                ["Interest-bearing debt", "$160,000", "Borrowings deducted through the net-debt bridge."],
                ["Net debt", "$65,000", "Interest-bearing debt less cash and bank."],
                ["Surplus assets", "$0", "No separately identified surplus or non-operating assets in the sample case."],
                ["Midpoint enterprise value", "$2,314,000", "Central DCF operating-business value after illiquidity adjustment."],
                ["Less: net debt", "($65,000)", "Deducted to move from enterprise value to shareholder value."],
                ["Add: surplus assets", "$0", "No surplus assets added in the sample case."],
                ["Midpoint equity value", "$2,249,000", "Central shareholder-value indication after the bridge."],
            ],
        },
        "valuation_summary_table": {
            "headers": ["Method / scenario", "Input", "Enterprise value", "Adjusted EV", "Equity value"],
            "rows": [
                ["DCF - high valuation", "9.9% WACC", "$3,209,000", "$2,831,000", "$2,766,000"],
                ["DCF - midpoint", "11.5% WACC", "$2,624,000", "$2,314,000", "$2,249,000"],
                ["DCF - low valuation", "13.4% WACC", "$2,152,000", "$1,898,000", "$1,833,000"],
                ["Multiples - low", "5.0x EBITDA", "$1,435,000", "$1,435,000", "$1,370,000"],
                ["Multiples - midpoint", "6.0x EBITDA", "$1,722,000", "$1,722,000", "$1,657,000"],
                ["Multiples - high", "7.0x EBITDA", "$2,009,000", "$2,009,000", "$1,944,000"],
            ],
        },
        "multiples_crosscheck_table": {
            "headers": ["Input", "Low", "Mid", "High"],
            "rows": [
                ["EV/EBITDA multiple", "5.0x", "6.0x", "7.0x"],
                ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
                ["Indicated enterprise value", "$1,435,000", "$1,722,000", "$2,009,000"],
            ],
        },
        "assumption_source_trail": {
            "headers": ["Assumption / input", "Value used", "Primary source", "Why it matters"],
            "rows": [
                [
                    "Normalised EBITDA",
                    "$287,000",
                    "Uploaded financial statements plus management-confirmed earnings adjustments",
                    "Sets the maintainable earnings base for DCF and multiples cross-checks.",
                ],
                [
                    "Explicit forecast period",
                    "5 years",
                    "AccountIQ valuation model convention",
                    "Defines the period over which cash flows are forecast before terminal value.",
                ],
                [
                    "Revenue and earnings growth",
                    "8.0%",
                    "Uploaded revenue history: CAGR capped between -5% and 12%",
                    "Drives the forecast cash-flow build and sensitivity matrix.",
                ],
                [
                    "Terminal growth",
                    "2.5%",
                    "Public research: New Zealand inflation input",
                    "Anchors long-term growth and must remain below the discount rate.",
                ],
                [
                    "WACC scenarios: high / mid / low valuation",
                    "9.9% / 11.5% / 13.4%",
                    "Public research: RBNZ risk-free rate and Damodaran ERP/beta",
                    "Discounts forecast cash flows and creates the valuation range.",
                ],
                [
                    "Maintenance capital expenditure",
                    "$25,000",
                    "Uploaded financial statements: depreciation proxy",
                    "Converts EBITDA into free cash flow by allowing for asset reinvestment.",
                ],
                [
                    "Operating working capital ratio",
                    "5.0%",
                    "Uploaded balance sheet: operating working-capital line items",
                    "Captures the cash investment required to support revenue growth.",
                ],
                [
                    "Debt, cash and surplus assets",
                    "Debt $160,000; cash $95,000; surplus assets $0",
                    "Debt: uploaded balance sheet borrowings where extracted; cash: uploaded balance sheet cash balance; surplus assets: no management-supplied amount identified",
                    "Bridges enterprise value to indicative equity value.",
                ],
                [
                    "Owner or key-person dependency",
                    "Responsibility is shared across leadership and team",
                    "Management-confirmed private input",
                    "Informs transition risk, key-person exposure and continuity planning.",
                ],
                [
                    "Largest-customer concentration",
                    "10% to 25%",
                    "Management-confirmed private input",
                    "Highlights concentration risk that is not usually visible online.",
                ],
                [
                    "Revenue predictability",
                    "A mix of recurring and one-off revenue",
                    "Management-confirmed private input",
                    "Distinguishes contracted revenue from transactional or project income.",
                ],
                [
                    "Revenue outlook",
                    "No specific forecast provided; growth derived from uploaded financial history",
                    "Management-confirmed private input",
                    "Documents the short-term outlook used to support or derive the growth assumption.",
                ],
            ],
        },
        "comparable_evidence_table": {
            "headers": ["Evidence", "Date", "Metric / multiple", "Relevance and limitation", "Source"],
            "rows": [
                [
                    "Business services sector dataset",
                    "Current dataset",
                    "EV/EBITDA benchmark",
                    "Broad listed-company evidence; larger and more liquid than the subject",
                    "Damodaran Online - https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                ],
                [
                    "NZ private-company valuation context",
                    "Valuation date",
                    "Risk-free and inflation inputs",
                    "Supports discount-rate inputs, not a transaction multiple",
                    "Reserve Bank of New Zealand - https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
                ],
                [
                    "Subject company public profile",
                    "Valuation date",
                    "Operating and market context",
                    "Public profile information retained for company-fact corroboration",
                    "NZ Companies Office - https://companies-register.companiesoffice.govt.nz/",
                ],
            ],
        },
        "sources_table": {
            "headers": ["Source", "URL", "Supports / used for"],
            "rows": [
                [
                    "Reserve Bank of New Zealand, interest rates",
                    "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
                    "Risk-free-rate and discount-rate context",
                ],
                [
                    "Reserve Bank of New Zealand, inflation",
                    "https://www.rbnz.govt.nz/monetary-policy/about-monetary-policy/inflation",
                    "Long-term inflation and terminal-growth context",
                ],
                [
                    "Damodaran Online, data resources",
                    "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                    "Equity risk premium, beta and private-company valuation inputs",
                ],
                [
                    "NZ Companies Office",
                    "https://companies-register.companiesoffice.govt.nz/",
                    "Company public-profile corroboration",
                ],
            ],
        },
        "normalisation_schedule": {
            "headers": ["Label", "Amount ($)", "Rationale"],
            "rows": [
                ["Owner remuneration above market", "$35,000", "Replace with an arm's-length management cost"],
                ["One-off legal costs", "$12,000", "Non-recurring legal expenditure"],
                ["Normalised FY25 EBITDA", "$287,000", "Reported EBITDA plus confirmed adjustments"],
            ],
        },
        "sensitivity_matrix": {
            "adjusted_enterprise_value_rows": [
                {"growth_pct": 6.0, "high": 2_621_000, "mid": 2_147_000, "low": 1_765_000},
                {"growth_pct": 8.0, "high": 2_831_000, "mid": 2_314_000, "low": 1_898_000},
                {"growth_pct": 10.0, "high": 3_054_000, "mid": 2_492_000, "low": 2_040_000},
            ],
        },
        "sensitivity_table": {
            "headers": [
                "Growth assumption",
                "High valuation / 9.9% WACC",
                "Mid valuation / 11.5% WACC",
                "Low valuation / 13.4% WACC",
            ],
            "rows": [
                ["6.0%", "$2,621,000", "$2,147,000", "$1,765,000"],
                ["8.0% - base", "$2,831,000", "$2,314,000", "$1,898,000"],
                ["10.0%", "$3,054,000", "$2,492,000", "$2,040,000"],
            ],
        },
        "specific_risk_factors": {
            "headers": ["Specific risk factor", "Management input", "Valuation relevance", "Report treatment"],
            "rows": [
                [
                    "Owner or key-person transition",
                    "Responsibility is shared across leadership and team",
                    "Affects operating continuity, handover depth and confidence in maintainable earnings.",
                    "Moderate transition risk; diligence should confirm responsibilities and handover depth.",
                ],
                [
                    "Customer concentration",
                    "10% to 25%",
                    "Large customer exposure can increase earnings volatility and diligence risk.",
                    "Moderate concentration risk; review top-customer retention and contract terms.",
                ],
                [
                    "Revenue predictability",
                    "A mix of recurring and one-off revenue",
                    "Contracted or recurring revenue usually supports more reliable cash-flow forecasts.",
                    "Mixed recurring and project revenue creates moderate earnings visibility.",
                ],
                [
                    "Revenue outlook and pipeline",
                    "No specific forecast provided; growth derived from uploaded financial history",
                    "Growth expectations affect forecast cash flows and sensitivity cases.",
                    "Growth is derived from uploaded history rather than a management forecast; review pipeline evidence before reliance.",
                ],
                [
                    "Other private context",
                    "A key contract renews next year.",
                    "Captures risks or opportunities not normally visible in public research.",
                    "Management-supplied context should be confirmed and reflected in diligence, forecast cases or reliance limitations.",
                ],
            ],
        },
    }


def test_customer_safe_report_failure_message_hides_provider_and_prompt_terms():
    msg = _customer_safe_report_failure_message(
        RuntimeError(
            "OpenAI invalid_request_error returned an invalid JSON object "
            "after reading the system prompt for sk-ant-secret"
        ),
        "valuation_advisory",
    )

    assert "valuation report quality checks" in msg
    lowered = msg.lower()
    for forbidden in (
        "openai",
        "json",
        "system prompt",
        "sk-ant",
        "invalid_request_error",
    ):
        assert forbidden not in lowered


def test_complete_valuation_sample_passes_strict_validation():
    _validate_generated_report_content(
        _e2e_report_content("valuation_advisory"),
        "valuation_advisory",
    )
    _validate_valuation_report_figures(
        _e2e_report_content("valuation_advisory"),
        _sample_valuation_result(),
    )
    _enforce_valuation_professional_content_audit(
        _e2e_report_content("valuation_advisory"),
    )


def test_professional_content_audit_gate_blocks_report_completion(monkeypatch):
    def fake_content_audit(content):
        assert "executive_summary" in content
        return ReportQualityAudit(
            artifact="valuation_report_content",
            issues=(
                ReportQualityIssue(
                    "missing_valuation_methods",
                    "Report text does not cover required valuation methods.",
                ),
            ),
            metadata={"section_count": 21},
        )

    monkeypatch.setattr(main_module, "audit_valuation_report_content", fake_content_audit)

    with pytest.raises(ValueError, match="professional content audit"):
        _enforce_valuation_professional_content_audit(
            _e2e_report_content("valuation_advisory"),
        )


def test_parser_accepts_plain_and_fenced_json_without_inserting_placeholders():
    content = {"introduction": "A complete introduction for this report."}
    sections = ["introduction", "executive_summary"]

    assert _parse_json_from_response(json.dumps(content), sections) == content
    fenced = f"```json\n{json.dumps(content)}\n```"
    assert _parse_json_from_response(fenced, sections) == content


def test_parser_rejects_malformed_output_instead_of_creating_stub_sections():
    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_json_from_response("The report could not be returned as JSON.", ["introduction"])


def test_validation_rejects_missing_or_unexpected_sections():
    content = _e2e_report_content("valuation_advisory")
    missing = copy.deepcopy(content)
    del missing["executive_summary"]
    with pytest.raises(ValueError, match="missing required sections"):
        _validate_generated_report_content(missing, "valuation_advisory")

    unexpected = copy.deepcopy(content)
    unexpected["internal_notes"] = "This should never appear in the customer report."
    with pytest.raises(ValueError, match="unexpected sections"):
        _validate_generated_report_content(unexpected, "valuation_advisory")


def test_validation_requires_formal_valuation_introduction_framing():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["introduction"] = (
        "This indicative valuation gives a high-level estimate of the business value."
    )

    with pytest.raises(ValueError, match="formal report framing"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_valuation_disclaimer_reliance_and_compliance_framing():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["disclaimer"] = (
        "This valuation report gives a general estimate based on available information."
    )

    with pytest.raises(ValueError, match="disclaimer"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_about_business_valuations_explanatory_concepts():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["about_business_valuations"] = (
        "This section explains business valuation at a high level for the reader."
    )

    with pytest.raises(ValueError, match="About business valuations"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_valuation_methodology_core_methods():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["valuation_methodology"] = (
        "This section explains the method selected for this valuation."
    )

    with pytest.raises(ValueError, match="Valuation methodology"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_valuation_general_principles_core_assumptions():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["general_principles"] = (
        "This section provides broad assumptions used for the valuation."
    )

    with pytest.raises(ValueError, match="general principles"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_valuation_glossary_core_terms():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["glossary"] = (
        "DCF: A cash flow valuation method.\n"
        "Enterprise value: Business value before debt and cash.\n"
        "Equity value: Value attributable to shareholders."
    )

    with pytest.raises(ValueError, match="glossary"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_rejects_empty_tables_and_placeholder_content():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["financial_performance"]["table"]["rows"] = []
    with pytest.raises(ValueError, match="no table rows"):
        _validate_generated_report_content(content, "valuation_advisory")

    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["business_overview"] = "[Section not generated - please retry]"
    with pytest.raises(ValueError, match="placeholder"):
        _validate_generated_report_content(content, "valuation_advisory")

    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["market_position"]["narrative"] += "\n\nSector benchmark detail is TBD."
    with pytest.raises(ValueError, match="placeholder"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_rejects_client_facing_implementation_language_in_narrative():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["introduction"] += (
        "\n\nThe Python-built valuation schedule was copied from the prompt before writing."
    )

    with pytest.raises(ValueError, match="client-facing implementation language"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_rejects_client_facing_implementation_language_in_tables():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["valuation_assumptions"]["table"]["rows"][0][3] += (
        " Return this JSON object exactly as supplied by OpenAI."
    )

    with pytest.raises(ValueError, match="client-facing implementation language"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_rejects_unfinished_follow_up_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " Please provide additional information before this report can be completed."
    )

    with pytest.raises(ValueError, match="unfinished follow-up language"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_rejects_adviser_follow_up_instruction():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " Ask your accountant to provide more information before this report can be completed."
    )

    with pytest.raises(ValueError, match="unfinished follow-up language"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_real_source_urls_for_valuation():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["sources"]["table"]["rows"][0][1] = "Reserve Bank of New Zealand interest rates"
    with pytest.raises(ValueError, match="source URLs"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_source_support_descriptions_for_valuation():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["sources"]["table"]["rows"][0][2] = "Website"

    with pytest.raises(ValueError, match="source supports or is used for"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_urls_in_each_comparable_evidence_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["comparable_evidence"]["table"]["rows"][0][-1] = "Damodaran Online"

    with pytest.raises(ValueError, match="comparable evidence rows must include source URLs"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_rejects_report_that_drops_computed_dcf_value():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    dcf_rows = content["dcf_analysis"]["table"]["rows"]
    adjusted_ev_row = next(row for row in dcf_rows if row[0] == "Adjusted enterprise value")
    adjusted_ev_row[1] = "$999,999"

    with pytest.raises(ValueError, match="DCF high adjusted enterprise value"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_error_messages_do_not_expose_implementation_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    dcf_rows = content["dcf_analysis"]["table"]["rows"]
    adjusted_ev_row = next(row for row in dcf_rows if row[0] == "Adjusted enterprise value")
    adjusted_ev_row[1] = "$999,999"

    with pytest.raises(ValueError) as excinfo:
        _validate_valuation_report_figures(content, _sample_valuation_result())

    message = str(excinfo.value)
    assert "AccountIQ-calculated figure" in message
    assert "Python-computed" not in message
    assert "Python-built" not in message


def test_validation_requires_dcf_cash_flow_schedule():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    del content["dcf_analysis"]["cash_flow_schedule"]

    with pytest.raises(ValueError, match="cash_flow_schedule"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_assumption_source_trail_categories():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["valuation_assumptions"]["table"]["rows"]
    for row in rows:
        row[2] = row[2].replace("Management-confirmed", "Private")

    with pytest.raises(ValueError, match="management-confirmed private inputs"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_assumption_source_trail_private_fact_topics():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["valuation_assumptions"]["table"]["rows"]
    content["valuation_assumptions"]["table"]["rows"] = [
        row for row in rows if row[0] != "Revenue outlook"
    ]

    with pytest.raises(ValueError, match="revenue outlook"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_rejects_report_that_changes_python_assumption_source_trail_text():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["valuation_assumptions"]["table"]["rows"]
    growth_row = next(row for row in rows if row[0] == "Revenue and earnings growth")
    growth_row[2] = "Management estimate"

    with pytest.raises(ValueError, match="assumption/source trail table"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_drops_python_normalisation_schedule_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["normalisations_schedule"]["table"]["rows"]
    content["normalisations_schedule"]["table"]["rows"] = [
        row for row in rows if row[0] != "One-off legal costs"
    ]

    with pytest.raises(ValueError, match="One-off legal costs"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_changes_python_normalisation_rationale():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["normalisations_schedule"]["table"]["rows"]
    owner_salary_row = next(row for row in rows if row[0] == "Owner remuneration above market")
    owner_salary_row[2] = "Confirmed adjustment"

    with pytest.raises(ValueError, match="normalisation schedule table"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_changes_python_financial_performance_value():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["financial_performance"]["table"]["rows"][0][1] = "$999,999"

    with pytest.raises(ValueError, match="financial performance table row 1 column 2"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_drops_python_ratio_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["financial_ratio_analysis"]["table"]["rows"]
    content["financial_ratio_analysis"]["table"]["rows"] = [
        row for row in rows if row[0] != "Revenue growth"
    ]

    with pytest.raises(ValueError, match="Revenue growth"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_changes_python_balance_sheet_bridge():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["balance_sheet_summary"]["table"]["rows"][-1][1] = "$999,999"

    with pytest.raises(ValueError, match="balance sheet summary table row 24 column 2"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_drops_python_executive_summary_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["executive_summary"]["table"]["rows"]
    content["executive_summary"]["table"]["rows"] = [
        row for row in rows if row[0] != "Indicative equity value"
    ]

    with pytest.raises(ValueError, match="Indicative equity value"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_changes_python_valuation_summary_value():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["valuation_summary"]["table"]["rows"][4][4] = "$999,999"

    with pytest.raises(ValueError, match="valuation summary table row 5 column 5"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_drops_python_wacc_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["wacc_assumptions"]["table"]["rows"]
    content["wacc_assumptions"]["table"]["rows"] = [
        row for row in rows if row[0] != "Risk-free rate"
    ]

    with pytest.raises(ValueError, match="Risk-free rate"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_drops_python_dcf_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["dcf_analysis"]["table"]["rows"]
    content["dcf_analysis"]["table"]["rows"] = [
        row for row in rows if row[0] != "Base revenue"
    ]

    with pytest.raises(ValueError, match="Base revenue"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_drops_python_multiples_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["multiples_crosscheck"]["table"]["rows"]
    content["multiples_crosscheck"]["table"]["rows"] = [
        row for row in rows if row[0] != "EV/EBITDA multiple"
    ]

    with pytest.raises(ValueError, match="EV/EBITDA multiple"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_drops_python_comparable_evidence_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["comparable_evidence"]["table"]["rows"]
    content["comparable_evidence"]["table"]["rows"] = [
        row for row in rows if row[0] != "Business services sector dataset"
    ]

    with pytest.raises(ValueError, match="Business services sector dataset"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_drops_python_source_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["sources"]["table"]["rows"]
    content["sources"]["table"]["rows"] = [
        row for row in rows if row[0] != "Damodaran Online, data resources"
    ]

    with pytest.raises(ValueError, match="Damodaran Online"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_changes_comparable_evidence_limitation_text():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["comparable_evidence"]["table"]["rows"][0][3] = (
        "Directly comparable transaction evidence"
    )

    with pytest.raises(ValueError, match="comparable evidence table"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_changes_source_support_text():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["sources"]["table"]["rows"][2][2] = "General market information"

    with pytest.raises(ValueError, match="sources table"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_alters_python_source_url():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["sources"]["table"]["rows"][2][1] = "https://example.com/damodaran-data"

    with pytest.raises(ValueError, match="sources table"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_alters_python_comparable_evidence_url():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["comparable_evidence"]["table"]["rows"][0][-1] = (
        "Damodaran Online - https://example.com/damodaran-data"
    )

    with pytest.raises(ValueError, match="comparable evidence table"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_invents_extra_source_url():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["business_overview"] += (
        "\n\nAdditional unsupported reference: https://example.com/invented-market-source"
    )

    with pytest.raises(ValueError, match="source URLs not present"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_allows_supported_rounded_money_wording_in_narrative():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " The DCF midpoint is approximately $2.31 million before the equity bridge."
    )

    _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_unsupported_extra_dollar_amount_in_narrative():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " A strategic buyer could therefore justify a $9,999,999 valuation."
    )

    with pytest.raises(ValueError, match="dollar amounts not present"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_unsupported_extra_percentage_metric_in_narrative():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " A separate upside case could use a 99.9% growth assumption."
    )

    with pytest.raises(ValueError, match="percentage or multiple metrics not present"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_unsupported_extra_multiple_metric_in_narrative():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["multiples_crosscheck"]["narrative"] += (
        " An unsupported premium cross-check could imply 9.9x EBITDA."
    )

    with pytest.raises(ValueError, match="percentage or multiple metrics not present"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_invented_named_transaction_claim_in_narrative():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["comparable_evidence"]["narrative"] += (
        " ExampleCorp acquired TargetCo in 2025 as a directly relevant private-company deal."
    )

    with pytest.raises(ValueError, match="named transaction claims not present"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_allows_generic_transaction_principle_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["general_principles"] += (
        "\n\nThe valuation assumes an arm's-length transaction between informed parties."
    )

    _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_allows_supported_source_url_with_sentence_punctuation():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["business_overview"] += (
        "\n\nThe market context is cross-checked against the RBNZ source "
        "(https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates)."
    )

    _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_punctuated_invented_source_url():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["business_overview"] += (
        "\n\nAdditional unsupported reference: https://example.com/invented-market-source)."
    )

    with pytest.raises(ValueError, match="source URLs not present"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_requires_specific_risk_factor_table():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    del content["sensitivity_and_risks"]["specific_risk_factors"]

    with pytest.raises(ValueError, match="specific_risk_factors"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_requires_core_specific_risk_topics():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["sensitivity_and_risks"]["specific_risk_factors"]["rows"]
    content["sensitivity_and_risks"]["specific_risk_factors"]["rows"] = [
        row for row in rows if row[0] != "Customer concentration"
    ]

    with pytest.raises(ValueError, match="customer concentration"):
        _validate_generated_report_content(content, "valuation_advisory")


def test_validation_rejects_report_that_drops_python_sensitivity_table_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["sensitivity_and_risks"]["table"]["rows"]
    content["sensitivity_and_risks"]["table"]["rows"] = [
        row for row in rows if row[0] != "8.0% - base"
    ]

    with pytest.raises(ValueError, match="8.0% - base"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_changes_python_specific_risk_context():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["sensitivity_and_risks"]["specific_risk_factors"]["rows"]
    context_row = next(row for row in rows if row[0] == "Other private context")
    context_row[1] = "Not supplied"

    with pytest.raises(ValueError, match="specific risk factor table"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_drops_mid_case_fcff_schedule_value():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    fcff_row = next(
        row
        for row in content["dcf_analysis"]["cash_flow_schedule"]["rows"]
        if row[0] == "Free cash flow to firm"
    )
    fcff_row[1] = "$999,999"

    with pytest.raises(ValueError, match="DCF cash-flow schedule row 7"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_validation_rejects_report_that_renames_python_cash_flow_schedule_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    fcff_row = next(
        row
        for row in content["dcf_analysis"]["cash_flow_schedule"]["rows"]
        if row[0] == "Free cash flow to firm"
    )
    fcff_row[0] = "Cash flow after reinvestment"

    with pytest.raises(ValueError, match="DCF cash-flow schedule"):
        _validate_valuation_report_figures(content, _sample_valuation_result())


def test_schema_still_contains_full_expanded_valuation_report():
    assert SECTION_SCHEMAS["valuation_advisory"] == [
        "introduction",
        "executive_summary",
        "business_overview",
        "market_position",
        "about_business_valuations",
        "valuation_methodology",
        "financial_performance",
        "financial_ratio_analysis",
        "normalisations_schedule",
        "balance_sheet_summary",
        "valuation_assumptions",
        "wacc_assumptions",
        "dcf_analysis",
        "valuation_summary",
        "multiples_crosscheck",
        "sensitivity_and_risks",
        "comparable_evidence",
        "sources",
        "disclaimer",
        "general_principles",
        "glossary",
    ]
