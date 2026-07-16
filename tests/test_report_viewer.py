"""Unit tests for wizard_report_view section rendering (Phase 05.1 D-I4)."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import (
    _demo_report_content_from_inputs,
    _inline_report_html,
    _narrative_to_html,
    _render_cover_report_brief_html,
    _render_cover_report_basis_html,
    _render_cover_valuation_snapshot_html,
    _render_report_contents_html,
    _render_report_sections_html,
    _render_valuation_basis_html,
    _validate_generated_report_content,
    app,
)
from report_prompts import compute_bank_credit_figures


def test_renders_plain_string_section():
    html = _render_report_sections_html(
        {"introduction": "Hello world.\n\nSecond para."},
        ["introduction"],
    )
    assert '<h2><span class="section-number">01</span> Introduction</h2>' in html
    assert "<p>Hello world.</p>" in html
    assert "<p>Second para.</p>" in html
    assert "report-table" not in html


def test_renders_contents_with_accessible_section_numbers():
    html = _render_report_contents_html(
        {
            "introduction": "Intro text",
            "valuation_methodology": "Method text",
            "glossary": "Glossary text",
        },
        ["introduction", "missing_section", "valuation_methodology", "glossary"],
    )

    assert "aria-label='01 Introduction'" in html
    assert "aria-label='02 Valuation Methodology Adopted'" in html
    assert "aria-label='03 Glossary'" in html
    assert "<span class='contents-number'>01</span><span>Introduction</span>" in html
    assert "<span class='contents-number'>02</span><span>Valuation Methodology Adopted</span>" in html
    assert "<span class='contents-number'>03</span><span>Glossary</span>" in html
    assert "missing_section" not in html


def test_report_view_route_is_framed_as_browser_review_surface():
    app.openapi_schema = None
    operation = app.openapi()["paths"]["/wizard/report/{report_id}/view"]["get"]

    assert operation["description"] == (
        "Render a completed report as the browser review surface for the report pack."
    )
    assert "temporary viewer" not in operation["description"].lower()


def test_renders_dict_section_with_table():
    sections = {
        "wacc_assumptions": {
            "narrative": "WACC inputs were derived from research.",
            "table": {
                "headers": ["Component", "High", "Mid", "Low"],
                "rows": [["Risk-free rate", "4.8%", "4.8%", "4.8%"], ["WACC", "13.5%", "11.1%", "8.7%"]],
            },
        },
    }
    html = _render_report_sections_html(sections, ["wacc_assumptions"])
    assert "<table class='report-table'>" in html
    assert "<th>Component</th>" in html
    assert '<th class="numeric-cell">High</th>' in html
    assert "<td>Risk-free rate</td>" in html
    assert '<td class="numeric-cell">11.1%</td>' in html
    assert "WACC inputs were derived from research." in html


def test_renders_bank_credit_section_with_extra_tables_and_credit_kicker():
    sections = {
        "coverage_and_sensitivity": {
            "narrative": "Coverage remains above the lender threshold under the base case.",
            "table": {
                "headers": ["Case", "DSCR", "ICR"],
                "rows": [["Base", "2.07x", "6.00x"]],
            },
            "amortisation_profile_table": {
                "headers": ["Period", "Opening debt", "Closing debt"],
                "rows": [["Year 1", "$3,362,000", "$2,882,000"]],
            },
        },
    }

    html = _render_report_sections_html(
        sections,
        ["coverage_and_sensitivity"],
        "bank_credit_paper",
    )

    assert "AccountIQ bank credit paper" in html
    assert "Coverage Ratios &amp; Sensitivity" in html
    assert "P&amp;I leverage profile" in html
    assert "$3,362,000" in html
    assert "AccountIQ indicative valuation" not in html


def test_bank_credit_sections_do_not_render_valuation_reader_guidance():
    sections = {
        "executive_summary": {
            "narrative": "The credit paper summarises the requested facility and lender view.",
            "table": {
                "headers": ["Credit item", "Position", "Underwriting comment"],
                "rows": [["Requested facility", "$1,000,000", "Indicative lender screen"]],
            },
        },
        "disclaimer": "This credit paper is indicative only and is not a bank approval or commitment.",
    }

    html = _render_report_sections_html(
        sections,
        ["executive_summary", "disclaimer"],
        "bank_credit_paper",
    )

    assert "AccountIQ bank credit paper" in html
    assert "This credit paper is indicative only" in html
    assert "Reliance at a glance" not in html
    assert "Valuation conclusion at a glance" not in html
    assert "valuation purpose" not in html.lower()
    assert "indicative valuation pack" not in html.lower()


def test_demo_bank_credit_content_fills_required_sections_and_tables():
    figures = compute_bank_credit_figures(
        [
            {"canonical_key": "revenue", "statement": "pnl", "values": {"2024": 900000, "2025": 1000000}},
            {"canonical_key": "ebitda", "statement": "pnl", "values": {"2024": 180000, "2025": 240000}},
            {"canonical_key": "net_profit", "statement": "pnl", "values": {"2024": 110000, "2025": 150000}},
            {"canonical_key": "cash_and_bank", "statement": "bs", "values": {"2025": 95000}},
            {"canonical_key": "trade_debtors", "statement": "bs", "values": {"2025": 210000}},
            {"canonical_key": "inventory", "statement": "bs", "values": {"2025": 65000}},
            {"canonical_key": "fixed_assets_net", "statement": "bs", "values": {"2025": 185000}},
            {"canonical_key": "trade_creditors", "statement": "bs", "values": {"2025": 155000}},
        ],
        {
            "loan_purpose": "Acquisition funding and refinance",
            "amount_requested": 250000,
            "proposed_term_years": 5,
            "conservative_funding_cost_pct": 8.5,
            "lvr_percent": 60,
            "security_package": "fleet_and_property",
            "security_value": 450000,
            "repayment_profile": "principal_and_interest",
            "transaction_value": 500000,
            "equity_contribution": 250000,
            "source_of_repayment": "Operating cash flow",
        },
    )

    content = _demo_report_content_from_inputs(
        report_type="bank_credit_paper",
        company_name="Towing Example Ltd",
        financial_rows=[],
        valuation_result=None,
        bank_credit_figures=figures,
        credit_research_brief={"company_summary": "Towing Example is a towing operator."},
    )

    _validate_generated_report_content(content, "bank_credit_paper")
    assert content["sources_and_uses"]["table"]["rows"]
    assert content["coverage_and_sensitivity"]["amortisation_profile_table"]["rows"]
    assert content["balance_sheet_debt_capacity"]["debt_capacity_table"]["rows"]
    assert "selected package is Balanced" in content["proposed_covenants"]["narrative"]
    assert "screening-only" in content["recommendation"]["narrative"]


def test_renders_browser_report_table_captions_for_dense_schedules():
    sections = {
        "sources": {
            "narrative": "The source trail explains what each public source supports.",
            "table": {
                "headers": ["Source", "URL", "Supports / used for"],
                "rows": [
                    [
                        "Reserve Bank of New Zealand",
                        "https://www.rbnz.govt.nz/statistics",
                        "Risk-free-rate and New Zealand macroeconomic context",
                    ],
                ],
            },
        },
        "dcf_analysis": {
            "narrative": "The DCF schedule uses the computed mid-case forecast.",
            "table": {
                "headers": ["DCF item", "High valuation", "Mid valuation", "Low valuation"],
                "rows": [["Adjusted enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"]],
            },
            "cash_flow_schedule": {
                "headers": ["Mid-case forecast", "Year 1", "Year 2"],
                "rows": [["Free cash flow to firm", "$198,731", "$214,630"]],
            },
        },
    }

    html = _render_report_sections_html(sections, ["sources", "dcf_analysis"])

    assert "<caption>Sources and References detailed schedule</caption>" in html
    assert "<caption>Discounted Cash Flow Analysis detailed schedule</caption>" in html
    assert "<caption>Mid-case forecast cash-flow schedule</caption>" in html
    assert html.index("<caption>Sources and References detailed schedule</caption>") < html.index("<thead>")


def test_renders_valuation_reader_guidance_from_computed_tables():
    sections = {
        "business_overview": {
            "narrative": "The business context combines public research with management-confirmed private inputs.",
        },
        "market_position": {
            "narrative": "Public market evidence is cross-checked against company operating context.",
        },
        "valuation_methodology": {
            "narrative": (
                "Discounted cash flow is the primary method. Researched EV/EBITDA evidence "
                "provides an independent reasonableness cross-check."
            ),
        },
        "financial_performance": {
            "narrative": "Revenue and EBITDA have grown over the observed period.",
            "table": {
                "headers": ["Year ending March", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
                "rows": [
                    ["Revenue", "$980,000", "$1,110,000", "$1,250,000", "$1,350,000"],
                    ["EBITDA", "$165,000", "$205,000", "$240,000", "$259,000"],
                    ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                ],
            },
        },
        "financial_ratio_analysis": {
            "narrative": "Historical ratios show improving scale and operating leverage.",
            "table": {
                "headers": ["Ratio", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
                "rows": [
                    ["Revenue growth", "Not available", "13.3%", "12.6%", "8.0%"],
                    ["Gross margin", "60.0%", "61.5%", "63.0%", "63.0%"],
                    ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                    ["Net profit margin", "10.7%", "11.5%", "12.0%", "12.1%"],
                ],
            },
        },
        "normalisations_schedule": {
            "narrative": "Normalisations isolate maintainable operating earnings.",
            "table": {
                "headers": ["Adjustment", "Amount", "Rationale"],
                "rows": [
                    ["Owner remuneration above market", "$35,000", "Replace with an arm's-length management cost"],
                    ["One-off legal costs", "$12,000", "Non-recurring legal expenditure"],
                    ["Normalised FY25 EBITDA", "$287,000", "Reported EBITDA plus confirmed adjustments"],
                ],
            },
        },
        "valuation_assumptions": {
            "narrative": "The source trail distinguishes uploaded, management-confirmed, public and model inputs.",
            "table": {
                "headers": ["Assumption / input", "Value used", "Primary source", "Why it matters"],
                "rows": [
                    [
                        "Normalised EBITDA",
                        "$287,000",
                        "Uploaded financial statements plus management-confirmed earnings adjustments",
                        "Sets the maintainable earnings base for DCF and multiples cross-checks.",
                    ],
                    [
                        "Revenue and earnings growth",
                        "8.0%",
                        "Management outlook: modest growth",
                        "Sets the explicit forecast growth assumption.",
                    ],
                    [
                        "Terminal growth",
                        "2.5%",
                        "Public research: New Zealand inflation input",
                        "Supports the terminal value assumption.",
                    ],
                    [
                        "WACC scenarios: high / mid / low valuation",
                        "9.9% / 11.5% / 13.4%",
                        "Public research: RBNZ risk-free rate and Damodaran ERP/beta",
                        "Discounts the forecast cash flows.",
                    ],
                    [
                        "Explicit forecast period",
                        "5 years",
                        "AccountIQ valuation model convention",
                        "Keeps the forecast horizon consistent across reports.",
                    ],
                    [
                        "Owner or key-person dependency",
                        "Responsibility is shared across leadership and team",
                        "Management-confirmed private input",
                        "Informs specific risk commentary.",
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
                        "Modest growth",
                        "Management-confirmed private input",
                        "Documents the short-term outlook used to support the growth assumption.",
                    ],
                ],
            },
        },
        "wacc_assumptions": {
            "narrative": "WACC inputs were derived from public research.",
            "table": {
                "headers": ["Component", "High valuation", "Mid valuation", "Low valuation"],
                "rows": [
                    ["Risk-free rate", "4.4%", "4.4%", "4.4%"],
                    ["Equity risk premium", "5.6%", "5.9%", "6.2%"],
                    ["Industry total beta", "1.05", "1.20", "1.35"],
                    ["WACC", "9.9%", "11.5%", "13.4%"],
                    ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
                ],
            },
        },
        "balance_sheet_summary": {
            "narrative": "Enterprise value is bridged to equity value.",
            "table": {
                "headers": ["Balance sheet item", "Value"],
                "rows": [
                    ["Midpoint enterprise value", "$2,314,000"],
                    ["Less: net debt", "($65,000)"],
                    ["Midpoint equity value", "$2,249,000"],
                ],
            },
        },
        "multiples_crosscheck": {
            "narrative": "The market range is used as a reasonableness cross-check.",
            "table": {
                "headers": ["Input", "Low", "Mid", "High"],
                "rows": [
                    ["EV/EBITDA multiple", "5.0x", "6.0x", "7.0x"],
                    ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
                    ["Indicated enterprise value", "$1,435,000", "$1,722,000", "$2,009,000"],
                ],
            },
        },
        "dcf_analysis": {
            "narrative": "DCF bridge explains the forecast free cash flows.",
            "table": {
                "headers": ["DCF item", "High valuation", "Mid valuation", "Low valuation"],
                "rows": [
                    ["Enterprise value before illiquidity", "$3,209,000", "$2,624,000", "$2,152,000"],
                    ["Adjusted enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
                ],
            },
            "cash_flow_schedule": {
                "headers": ["Mid-case forecast", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
                "rows": [
                    ["Revenue", "$1,350,000", "$1,458,000", "$1,574,640", "$1,700,611", "$1,836,660"],
                    ["Free cash flow to firm", "$198,731", "$214,630", "$231,800", "$250,344", "$270,372"],
                    ["Discounted free cash flow", "$178,234", "$172,639", "$167,220", "$161,971", "$156,887"],
                ],
            },
        },
        "valuation_summary": {
            "narrative": "The DCF range is cross-checked against researched market multiples.",
            "table": {
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
        },
        "sensitivity_and_risks": {
            "narrative": "Sensitivity and qualitative risk are considered separately.",
            "table": {
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
                    ["Owner or key-person transition", "Shared", "Transition risk", "Confirm handover depth"],
                    ["Customer concentration", "10% to 25%", "Retention risk", "Review top customers"],
                    ["Revenue predictability", "Mixed", "Cash-flow certainty", "Review recurring revenue"],
                    ["Revenue outlook and pipeline", "Modest growth", "Forecast support", "Confirm pipeline"],
                    ["Other private context", "Key contract renewal", "Private risk", "Reflect in diligence"],
                ],
            },
        },
        "comparable_evidence": {
            "narrative": "Comparable public evidence is retained as a reasonableness cross-check.",
            "table": {
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
        },
        "sources": {
            "narrative": "Sources support the valuation assumptions.",
            "table": {
                "headers": ["Source", "URL", "Supports / used for"],
                "rows": [
                    [
                        "Reserve Bank of New Zealand",
                        "https://www.rbnz.govt.nz/statistics",
                        "Risk-free-rate and discount-rate context",
                    ],
                    [
                        "RBNZ inflation",
                        "https://www.rbnz.govt.nz/inflation",
                        "Long-term inflation and terminal-growth context",
                    ],
                    [
                        "Companies Office",
                        "https://companies-register.companiesoffice.govt.nz",
                        "Company public-profile corroboration",
                    ],
                ],
            },
        },
        "disclaimer": (
            "## Indicative purpose and reliance\n"
            "This report is indicative only and has been prepared solely for the stated valuation "
            "purpose. It does not constitute financial advice and should not be relied upon as a "
            "substitute for independent professional, legal, tax or accounting advice. No responsibility "
            "is accepted to any third party who obtains or relies on this report.\n\n"
            "## Information and valuation date\n"
            "The analysis relies on management-supplied information, extracted financial records and "
            "identified public sources. Those inputs have not been independently audited."
        ),
    }

    html = _render_report_sections_html(
        sections,
        [
            "business_overview",
            "market_position",
            "valuation_methodology",
            "financial_performance",
            "financial_ratio_analysis",
            "normalisations_schedule",
            "valuation_assumptions",
            "wacc_assumptions",
            "dcf_analysis",
            "valuation_summary",
            "multiples_crosscheck",
            "balance_sheet_summary",
            "sensitivity_and_risks",
            "comparable_evidence",
            "sources",
            "disclaimer",
        ],
    )

    assert 'class="reader-guidance"' in html
    assert "Business context at a glance" in html
    assert "<dt>Owner or key-person dependency</dt>" in html
    assert "<dd>Responsibility is shared across leadership and team</dd>" in html
    assert "<dt>Customer concentration</dt>" in html
    assert "<dd>10% to 25%</dd>" in html
    assert "<dt>Revenue predictability</dt>" in html
    assert "<dd>A mix of recurring and one-off revenue</dd>" in html
    assert "<dt>Revenue outlook</dt>" in html
    assert "<dd>Modest growth</dd>" in html
    assert "Market context at a glance" in html
    assert "<dt>Public sources retained</dt>" in html
    assert "<dd>6</dd>" in html
    assert "<dt>Benchmark evidence</dt>" in html
    assert "<dd>Public evidence supports sector or EV/EBITDA context</dd>" in html
    assert "<dt>Public profile support</dt>" in html
    methodology_section_start = html.index('id="valuation_methodology"')
    method_selection_index = html.index("Valuation approach selection", methodology_section_start)
    methodology_panel_index = html.index("Methodology at a glance", methodology_section_start)
    assert methodology_panel_index < method_selection_index
    assert 'aria-label="Valuation approach selection"' in html
    assert "<td>Income approach - DCF</td>" in html
    assert "<td>Adopted as primary</td>" in html
    assert "<td>Market approach - EV/EBITDA</td>" in html
    assert "<td>Reasonableness cross-check</td>" in html
    assert "<td>Asset approach / net assets</td>" in html
    assert "<td>Not primary</td>" in html
    assert "Methodology at a glance" in html
    assert "<dt>Primary valuation method</dt>" in html
    assert "<dd>Discounted cash flow</dd>" in html
    assert "<dt>Discount-rate range</dt>" in html
    assert "<dd>9.9% - 13.4%</dd>" in html
    assert "<dt>Market cross-check</dt>" in html
    assert "<dd>5.0x - 7.0x EV/EBITDA</dd>" in html
    assert "Trading performance at a glance" in html
    assert "<dt>Revenue bridge</dt>" in html
    assert "<dd>$980,000 to $1,350,000</dd>" in html
    financial_section_start = html.index('id="financial_performance"')
    trading_panel_index = html.index(
        "Trading performance at a glance",
        financial_section_start,
    )
    financial_table_index = html.index(
        "<table class='report-table'>",
        financial_section_start,
    )
    assert trading_panel_index < financial_table_index
    assert 'aria-label="Financial trend visual"' in html
    assert "Revenue and EBITDA trend from the uploaded-financials schedule." in html
    assert "FY23 Actual" in html
    assert "$980,000" in html
    assert "$165,000" in html
    assert "Margin and growth at a glance" in html
    assert "<dt>Latest revenue growth</dt>" in html
    assert "<dd>8.0%</dd>" in html
    ratio_section_start = html.index('id="financial_ratio_analysis"')
    margin_panel_index = html.index(
        "Margin and growth at a glance",
        ratio_section_start,
    )
    ratio_table_index = html.index(
        "<table class='report-table'>",
        ratio_section_start,
    )
    assert margin_panel_index < ratio_table_index
    normalisations_section_start = html.index('id="normalisations_schedule"')
    normalised_bridge_index = html.index("Normalised EBITDA bridge", normalisations_section_start)
    normalisations_table_index = html.index("<table class='report-table'>", normalisations_section_start)
    assert normalised_bridge_index < normalisations_table_index
    assert 'aria-label="Normalised EBITDA bridge"' in html
    assert "<strong>Uploaded EBITDA basis</strong>" in html
    assert "<span>$240,000</span>" in html
    assert "<strong>Net normalisation</strong>" in html
    assert "<span>$47,000</span>" in html
    assert "<strong>Normalised EBITDA</strong>" in html
    assert "<span>$287,000</span>" in html
    assert "Normalisation impact at a glance" in html
    normalisation_panel_index = html.index(
        "Normalisation impact at a glance",
        normalisations_section_start,
    )
    assert normalisation_panel_index < normalisations_table_index
    assert "<dt>Net EBITDA adjustment</dt>" in html
    assert "<dd>$47,000</dd>" in html
    assert "Assumption basis at a glance" in html
    assert "<dt>Maintainable earnings base</dt>" in html
    assert "<dd>$287,000</dd>" in html
    assert "<dt>Public research inputs</dt>" in html
    assert "<dd>2</dd>" in html
    assumptions_section_start = html.index('id="valuation_assumptions"')
    assumption_panel_index = html.index("Assumption basis at a glance", assumptions_section_start)
    assumption_table_index = html.index("<table class='report-table'>", assumptions_section_start)
    assert assumption_panel_index < assumption_table_index
    assert "How the discount rate drives the range" in html
    assert "<dt>High valuation discount rate</dt>" in html
    assert "<dd>9.9%</dd>" in html
    wacc_section_start = html.index('id="wacc_assumptions"')
    wacc_panel_index = html.index("How the discount rate drives the range", wacc_section_start)
    wacc_visual_index = html.index("WACC build visual", wacc_section_start)
    wacc_table_index = html.index("<table class='report-table'>", wacc_section_start)
    assert wacc_panel_index < wacc_table_index
    assert wacc_visual_index < wacc_table_index
    assert 'aria-label="WACC build visual"' in html
    assert "<strong>Risk-free rate</strong>" in html
    assert "<span>4.4%</span>" in html
    assert "<strong>Beta-adjusted risk premium</strong>" in html
    assert "<span>7.1%</span>" in html
    assert "<strong>Mid WACC</strong>" in html
    assert "<span>11.5%</span>" in html
    assert "WACC, beta and equity-risk-premium assumptions are derived and disclosed as valuation-model inputs." in html
    assert "How the market cross-check is used" in html
    assert "<dt>Market multiple range</dt>" in html
    assert "<dd>5.0x - 7.0x</dd>" in html
    multiples_section_start = html.index('id="multiples_crosscheck"')
    multiples_panel_index = html.index("How the market cross-check is used", multiples_section_start)
    implied_multiple_index = html.index("Implied multiple reconciliation", multiples_section_start)
    multiples_table_index = html.index("<table class='report-table'>", multiples_section_start)
    assert multiples_panel_index < multiples_table_index
    assert implied_multiple_index < multiples_table_index
    assert 'aria-label="Implied multiple reconciliation"' in html
    assert "<strong>Normalised EBITDA</strong>" in html
    assert "<span>$287,000</span>" in html
    assert "<strong>Market EV/EBITDA range</strong>" in html
    assert "<span>5.0x - 7.0x</span>" in html
    assert "<strong>DCF post-illiquidity range</strong>" in html
    assert "<span>6.6x - 9.9x</span>" in html
    assert "<strong>Cross-check tension</strong>" in html
    assert "<span>2.1x above market midpoint</span>" in html
    balance_section_start = html.index('id="balance_sheet_summary"')
    bridge_panel_index = html.index("Enterprise-to-equity bridge", balance_section_start)
    bridge_visual_index = html.index("Enterprise-to-equity visual", balance_section_start)
    balance_table_index = html.index("<table class='report-table'>", balance_section_start)
    assert bridge_panel_index < balance_table_index
    assert bridge_visual_index < balance_table_index
    assert 'aria-label="Enterprise-to-equity visual"' in html
    assert "Shows how operating-business value converts to shareholder value" in html
    assert "<strong>Midpoint enterprise value</strong>" in html
    assert "<span>$2,314,000</span>" in html
    assert "<strong>Less net debt</strong>" in html
    assert "<span>($65,000)</span>" in html
    dcf_section_start = html.index('id="dcf_analysis"')
    dcf_forecast_panel_index = html.index("DCF forecast bridge at a glance", dcf_section_start)
    dcf_value_build_index = html.index("DCF value build visual", dcf_section_start)
    dcf_table_index = html.index("<table class='report-table'>", dcf_section_start)
    assert dcf_forecast_panel_index < dcf_table_index
    assert dcf_value_build_index < dcf_table_index
    assert 'aria-label="DCF value build visual"' in html
    assert "Shows how the mid-case discounted cash flows and terminal value" in html
    assert "<strong>PV explicit FCFF</strong>" in html
    assert "<span>$836,951</span>" in html
    assert "<strong>PV terminal value</strong>" in html
    assert "<span>$1,787,049</span>" in html
    assert "<strong>Illiquidity discount</strong>" in html
    assert "<span>$310,000</span>" in html
    assert "DCF forecast bridge at a glance" in html
    assert "<dt>Revenue forecast bridge</dt>" in html
    assert "<dd>$1,350,000 to $1,836,660</dd>" in html
    assert "Valuation range at a glance" in html
    assert "<dt>Primary DCF range</dt>" in html
    assert "<dd>$1,898,000 - $2,831,000</dd>" in html
    assert "<dt>DCF vs multiple midpoint</dt>" in html
    assert "<dd>$592,000 above</dd>" in html
    valuation_summary_section_start = html.index('id="valuation_summary"')
    valuation_summary_panel_index = html.index(
        "Valuation range at a glance",
        valuation_summary_section_start,
    )
    valuation_summary_table_index = html.index(
        "<table class='report-table'>",
        valuation_summary_section_start,
    )
    assert valuation_summary_panel_index < valuation_summary_table_index
    assert "Sensitivity takeaway at a glance" in html
    sensitivity_section_start = html.index('id="sensitivity_and_risks"')
    sensitivity_panel_index = html.index(
        "Sensitivity takeaway at a glance",
        sensitivity_section_start,
    )
    sensitivity_table_index = html.index(
        "<table class='report-table'>",
        sensitivity_section_start,
    )
    assert sensitivity_panel_index < sensitivity_table_index
    assert 'aria-label="Sensitivity spread visual"' in html
    assert "Downside, base and upside adjusted enterprise value from AccountIQ&#x27;s sensitivity analysis." in html
    assert "Base $2,314,000" in html
    assert "<dt>Base sensitivity case</dt>" in html
    assert "<dd>$2,314,000</dd>" in html
    assert "<dt>Quantified EV span</dt>" in html
    assert "<dd>$1,765,000 - $3,054,000</dd>" in html
    assert "<dt>Specific risk factors</dt>" in html
    assert "<dd>5</dd>" in html
    assert "Comparable evidence at a glance" in html
    assert "<dt>Evidence rows</dt>" in html
    assert "<dd>3</dd>" in html
    assert "<dt>Comparability caveat</dt>" in html
    assert "<dd>Limitations explained as a reasonableness check</dd>" in html
    comparable_section_start = html.index('id="comparable_evidence"')
    comparable_panel_index = html.index(
        "Comparable evidence at a glance",
        comparable_section_start,
    )
    comparable_table_index = html.index(
        "<table class='report-table'>",
        comparable_section_start,
    )
    assert comparable_panel_index < comparable_table_index
    assert "Enterprise-to-equity bridge" in html
    assert "<dt>Net debt bridge</dt>" in html
    assert "<dd>($65,000)</dd>" in html
    assert "Source trail at a glance" in html
    assert "<dt>Public URLs retained</dt>" in html
    assert "<dd>3</dd>" in html
    assert "<dt>Discount-rate support</dt>" in html
    assert "<dd>Public sources retained for WACC inputs</dd>" in html
    sources_section_start = html.index('id="sources"')
    source_trail_panel_index = html.index(
        "Source trail at a glance",
        sources_section_start,
    )
    sources_table_index = html.index(
        "<table class='report-table'>",
        sources_section_start,
    )
    assert source_trail_panel_index < sources_table_index
    assert "Reliance at a glance" in html
    assert "<dt>Intended use</dt>" in html
    assert "<dd>Stated purpose only</dd>" in html
    assert "<dt>Advice status</dt>" in html
    assert "<dd>Not advice</dd>" in html
    assert "<dt>Third-party reliance</dt>" in html
    assert "<dd>No responsibility accepted</dd>" in html
    disclaimer_section_start = html.index('id="disclaimer"')
    reliance_panel_index = html.index(
        "Reliance at a glance",
        disclaimer_section_start,
    )
    disclaimer_narrative_index = html.index(
        "Indicative purpose and reliance",
        disclaimer_section_start,
    )
    assert reliance_panel_index < disclaimer_narrative_index


def test_escapes_html_in_table_cells():
    sections = {
        "valuation_summary": {
            "narrative": "Result <script>alert(1)</script>",
            "table": {"headers": ["A<x>"], "rows": [["<b>bold</b>"]]},
        },
    }
    html = _render_report_sections_html(sections, ["valuation_summary"])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<th>A<x></th>" not in html
    assert "&lt;x&gt;" in html
    assert "<td><b>bold</b></td>" not in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html


def test_links_source_urls_without_unescaping_html():
    sections = {
        "sources": (
            "RBNZ rates: https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates\n"
            "<script>alert(1)</script>"
        )
    }

    html = _render_report_sections_html(sections, ["sources"])

    assert 'class="report-section section-sources"' in html
    assert (
        '<a href="https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates" '
        'target="_blank" rel="noopener noreferrer">'
        "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates</a>"
    ) in html
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_inline_report_html_keeps_trailing_punctuation_outside_source_links():
    html = _inline_report_html(
        "RBNZ evidence (https://www.rbnz.govt.nz/statistics). <script>alert(1)</script>"
    )

    assert (
        '<a href="https://www.rbnz.govt.nz/statistics" target="_blank" '
        'rel="noopener noreferrer">https://www.rbnz.govt.nz/statistics</a>'
    ) in html
    assert "</a>)." in html
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_links_source_urls_inside_report_tables():
    sections = {
        "comparable_evidence": {
            "narrative": "Comparable evidence is indicative.",
            "table": {
                "headers": ["Evidence", "Source"],
                "rows": [["RBNZ", "https://www.rbnz.govt.nz/statistics"]],
            },
        },
    }

    html = _render_report_sections_html(sections, ["comparable_evidence"])

    assert 'class="report-section section-comparable-evidence"' in html
    assert '<a href="https://www.rbnz.govt.nz/statistics"' in html
    assert "<td>https://www.rbnz.govt.nz/statistics</td>" not in html


def test_renders_sources_as_structured_table():
    sections = {
        "sources": {
            "narrative": "Sources are retained for auditability.",
            "table": {
                "headers": ["Source", "URL", "Supports / used for"],
                "rows": [["RBNZ", "https://www.rbnz.govt.nz/statistics", "Risk-free rate"]],
            },
        }
    }

    html = _render_report_sections_html(sections, ["sources"])

    assert "<th>URL</th>" in html
    assert "<td>Risk-free rate</td>" in html
    assert '<a href="https://www.rbnz.govt.nz/statistics"' in html


def test_browser_report_tables_only_right_align_numeric_columns():
    sections = {
        "valuation_assumptions": {
            "narrative": "Assumptions distinguish sources and why each input matters.",
            "table": {
                "headers": ["Assumption / input", "Value used", "Primary source", "Why it matters"],
                "rows": [
                    [
                        "Normalised EBITDA",
                        "$287,000",
                        "Uploaded financial statements plus management-confirmed earnings adjustments",
                        "Sets the maintainable earnings base for DCF and multiples cross-checks.",
                    ],
                    [
                        "Owner or key-person dependency",
                        "Responsibility is shared across leadership and team",
                        "Management-confirmed private input",
                        "Informs specific risk commentary and continuity planning.",
                    ],
                    [
                        "Revenue predictability",
                        "A mix of recurring and one-off revenue",
                        "Management-confirmed private input",
                        "Distinguishes contracted revenue from transactional or project income.",
                    ],
                ],
            },
        },
        "normalisations_schedule": {
            "narrative": "Normalisations were confirmed by the owner.",
            "table": {
                "headers": ["Label", "Amount ($)", "Rationale"],
                "rows": [["Owner salary", "$50,000", "Above-market owner salary adjustment"]],
            },
        },
    }

    assumptions_html = _render_report_sections_html(sections, ["valuation_assumptions"])
    normalisations_html = _render_report_sections_html(sections, ["normalisations_schedule"])

    assert "numeric-cell" not in assumptions_html
    assert '<th class="numeric-cell">Amount ($)</th>' in normalisations_html
    assert '<td class="numeric-cell">$50,000</td>' in normalisations_html
    assert '<td class="numeric-cell">Above-market owner salary adjustment</td>' not in normalisations_html


def test_handles_missing_table_data():
    sections = {"foo": {"narrative": "ok"}}
    html = _render_report_sections_html(sections, ["foo"])
    assert "<p>ok</p>" in html
    assert "<table" not in html


def test_renders_dcf_cash_flow_schedule_table():
    sections = {
        "dcf_analysis": {
            "narrative": "DCF bridge explains the forecast free cash flows.",
            "table": {
                "headers": ["DCF item", "High", "Mid", "Low"],
                "rows": [["WACC", "9.9%", "11.5%", "13.4%"]],
            },
            "cash_flow_schedule": {
                "headers": ["Mid-case forecast", "Year 1", "Year 2"],
                "rows": [["Free cash flow to firm", "$198,731", "$214,630"]],
            },
        }
    }

    html = _render_report_sections_html(sections, ["dcf_analysis"])

    assert "Mid-case forecast cash-flow schedule" in html
    assert html.count("<table class='report-table'>") == 2
    assert "<th>Mid-case forecast</th>" in html
    assert "<td>Free cash flow to firm</td>" in html
    assert '<td class="numeric-cell">$198,731</td>' in html


def test_renders_specific_risk_factor_table():
    sections = {
        "sensitivity_and_risks": {
            "narrative": "Sensitivity and qualitative risk are considered separately.",
            "table": {
                "headers": ["Growth assumption", "High", "Mid", "Low"],
                "rows": [["8.0% - base", "$2,831,000", "$2,314,000", "$1,898,000"]],
            },
            "specific_risk_factors": {
                "headers": ["Specific risk factor", "Management input", "Valuation relevance", "Report treatment"],
                "rows": [["Customer concentration", "10 to 25", "Retention risk", "Review top customer terms"]],
            },
        }
    }

    html = _render_report_sections_html(sections, ["sensitivity_and_risks"])

    assert "Specific risk factors" in html
    assert html.count("<table class='report-table'>") == 2
    assert "<th>Specific risk factor</th>" in html
    assert "<td>Customer concentration</td>" in html


def test_handles_empty_section_value():
    sections = {"foo": ""}
    html = _render_report_sections_html(sections, ["foo"])
    assert '<h2><span class="section-number">01</span> Foo</h2>' in html
    assert "<p></p>" not in html


def test_renders_cover_valuation_snapshot_from_report_table():
    sections = {
        "executive_summary": {
            "narrative": "Summary.",
            "table": {
                "headers": ["Indicative valuation", "High", "Mid", "Low"],
                "rows": [
                    ["Enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
                    ["Less: net debt", "$65,000", "$65,000", "$65,000"],
                    ["Indicative equity value", "$2,766,000", "$2,249,000", "$1,833,000"],
                ],
            },
        },
    }

    html = _render_cover_valuation_snapshot_html(sections)

    assert 'aria-label="Valuation snapshot"' in html
    assert "<span>Valuation snapshot</span>" in html
    assert "<th>High</th>" in html
    assert "<td>Enterprise value</td>" in html
    assert "<td>$2,314,000</td>" in html
    assert "Computed from the same valuation table" in html


def test_renders_executive_summary_highlights_from_report_table():
    sections = {
        "executive_summary": {
            "narrative": "The primary DCF analysis indicates the valuation range.",
            "table": {
                "headers": ["Indicative valuation", "High", "Mid", "Low"],
                "rows": [
                    ["Enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
                    ["Less: net debt", "$65,000", "$65,000", "$65,000"],
                    ["Indicative equity value", "$2,766,000", "$2,249,000", "$1,833,000"],
                ],
            },
        },
    }

    html = _render_report_sections_html(sections, ["executive_summary"])

    assert 'aria-label="Valuation conclusion at a glance"' in html
    assert "Valuation conclusion at a glance" in html
    assert "Enterprise value range" in html
    assert "$1,898,000 - $2,831,000" in html
    assert "Midpoint enterprise value" in html
    assert "$2,314,000" in html
    assert "Midpoint equity value" in html
    assert "$2,249,000" in html
    assert 'aria-label="Valuation range visual"' in html
    assert "Low, midpoint and high cases from AccountIQ&#x27;s valuation schedules." in html
    assert "Operating-business value before the net-debt bridge." in html
    assert "Mid $2,314,000" in html
    assert "Shareholder-value range after debt, cash and surplus assets." in html
    assert "Mid $2,249,000" in html


def test_cover_valuation_snapshot_escapes_table_values():
    sections = {
        "executive_summary": {
            "table": {
                "headers": ["Indicative valuation", "<High>", "Mid", "Low"],
                "rows": [["Enterprise value <script>", "$1", "$2", "$3"]],
            },
        },
    }

    html = _render_cover_valuation_snapshot_html(sections)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<th><High></th>" not in html
    assert "&lt;High&gt;" in html


def test_renders_professional_cover_brief_without_extra_questions():
    html = _render_cover_report_brief_html(
        company_name="Acme & Sons <script>",
        report_label="Indicative Valuation Report",
        report_id=42,
        generated_at="2026-07-04 09:15:00",
        valuation_purpose="Prepare for a sale or transaction",
        demo_mode=False,
    )

    assert 'aria-label="Report cover details"' in html
    assert "<dt>Prepared for</dt>" in html
    assert "Acme &amp; Sons &lt;script&gt;" in html
    assert "<script>" not in html
    assert "<dt>Prepared by</dt>" in html
    assert "<dd>AccountIQ</dd>" in html
    assert "<dt>Reference</dt>" in html
    assert "<dd>AIQ-VAL-000042</dd>" in html
    assert "<dt>Purpose</dt>" in html
    assert "Prepare for a sale or transaction" in html
    assert "<dt>Basis of value</dt>" in html
    assert "Indicative fair-market value, going-concern basis" in html
    assert "Indicative valuation support only" in html


def test_cover_brief_labels_demo_reports_as_not_for_reliance():
    html = _render_cover_report_brief_html(
        company_name="Demo Co",
        report_label="Demo Indicative Valuation Report",
        report_id=7,
        demo_mode=True,
    )

    assert "Demo data only - not for reliance." in html
    assert "Indicative valuation support only" not in html


def test_renders_cover_report_basis_without_extra_questions():
    html = _render_cover_report_basis_html()

    assert 'aria-label="Report basis"' in html
    assert "<span>Report basis</span>" in html
    assert "<dt>Uploaded financials</dt>" in html
    assert "Revenue, earnings and balance sheet" in html
    assert "<dt>Five private inputs</dt>" in html
    assert "Only facts management can confirm" in html
    assert "<dt>Public-source trail</dt>" in html
    assert "Research URLs retained for review" in html
    assert "<dt>AccountIQ model</dt>" in html
    assert "DCF, WACC, multiples and sensitivity" in html
    assert "questionnaire" not in html.lower()


def test_renders_valuation_basis_front_matter_without_extra_questions():
    html = _render_valuation_basis_html(
        demo_mode=False,
        valuation_purpose="Prepare for a sale or transaction",
        generated_at="2026-07-04 09:15:00",
        intake_answers={
            "valuation_purpose": "sale_or_transaction",
            "owner_dependency": "shared",
            "customer_concentration": "10_to_25",
            "revenue_quality": "mixed",
            "revenue_outlook": "not_sure",
            "company_website": "https://example.co.nz",
            "company_location": "Auckland, New Zealand",
            "public_source_urls": ["https://www.linkedin.com/company/example"],
            "private_context": "A key contract renews next year.",
        },
    )

    assert 'id="basis-of-preparation"' in html
    assert 'aria-labelledby="basis-of-preparation-title"' in html
    assert "Basis of preparation" in html
    assert "Report letter" in html
    assert "professional valuation report pack" in html
    assert "without requiring the owner to complete a long technical valuation questionnaire" in html
    assert "Prepared for" in html
    assert "Prepared by" in html
    assert "AccountIQ valuation team" in html
    assert "Preparer role" in html
    assert "Report channel" in html
    assert "AccountIQ" in html
    assert "Purpose and reliance" in html
    assert "Important limitation" in html
    assert "not an audit or assurance engagement" in html
    assert "Valuation purpose" in html
    assert "Prepare for a sale or transaction" in html
    assert "Valuation date" in html
    assert "4 July 2026" in html
    assert "Indicative fair-market value" in html
    assert "Information basis" in html
    assert "uploaded financial statements" in html
    assert "earnings-adjustment review" in html
    assert "public-source research" in html
    assert "Scope exclusions" in html
    assert "audit, assurance engagement, legal advice, tax advice" in html
    assert "AccountIQ valuation calculations" in html
    assert "model-computed" not in html
    assert "Python-computed" not in html
    assert "Uploaded financial statements" in html
    assert "Five management-confirmed private inputs" in html
    assert "Management input trail" in html
    assert "<th>Basis</th>" in html
    assert html.count("Management-confirmed private input") >= 5
    assert "Management input - Valuation purpose" in html
    assert "Prepare for a sale or transaction" in html
    assert "Management input - Owner or key-person dependency" in html
    assert "Responsibility is shared across leadership and team" in html
    assert "Management input - Largest-customer concentration" in html
    assert "10% to 25%" in html
    assert "Management input - Revenue predictability" in html
    assert "A mix of recurring and one-off revenue" in html
    assert "Management input - Revenue outlook" in html
    assert "No specific forecast provided; growth derived from uploaded financial history" in html
    assert "when no specific forecast is supplied" in html
    assert "Evidence and model basis" in html
    assert "Earnings-adjustment review" in html
    assert "Optional public-source hints" in html
    assert "not required from management" in html
    assert "Research hints provided" in html
    assert "Website:" in html
    assert '<a href="https://example.co.nz"' in html
    assert "Location: Auckland, New Zealand" in html
    assert '<a href="https://www.linkedin.com/company/example"' in html
    assert "Private valuation context: A key contract renews next year." in html
    assert "AccountIQ calculates the DCF valuation" in html
    assert "discount-rate scenarios" in html
    assert "Derived technical assumptions" in html
    assert "Discount rate, terminal growth and forecast horizon" in html
    assert "rather than selected by management" in html
    assert "Questions intentionally not asked" in html
    assert "not asked to choose the forecast horizon, WACC, terminal growth or discount-rate scenarios" in html


def test_valuation_basis_front_matter_orders_management_trail_before_evidence_basis():
    html = _render_valuation_basis_html(
        demo_mode=False,
        valuation_purpose="Prepare for a sale or transaction",
        intake_answers={
            "valuation_purpose": "sale_or_transaction",
            "owner_dependency": "shared",
            "customer_concentration": "10_to_25",
            "revenue_quality": "mixed",
            "revenue_outlook": "not_sure",
        },
    )

    management_trail_index = html.index("Management input trail")
    report_letter_index = html.index("Report letter")
    scope_exclusions_index = html.index("Scope exclusions")
    owner_dependency_index = html.index("Management input - Owner or key-person dependency")
    evidence_basis_index = html.index("Evidence and model basis")
    technical_assumptions_index = html.index("Derived technical assumptions")

    assert report_letter_index < scope_exclusions_index < management_trail_index
    assert management_trail_index < owner_dependency_index < evidence_basis_index
    assert evidence_basis_index < technical_assumptions_index
    assert html.count("Management-confirmed private input") >= 5


def test_valuation_basis_front_matter_labels_demo_research():
    html = _render_valuation_basis_html(demo_mode=True)

    assert "Simulated public research" in html
    assert "Public research and source trail" not in html


# ---------------------------------------------------------------------------
# _narrative_to_html tests
# ---------------------------------------------------------------------------

def test_narrative_heading_renders_h3():
    html = _narrative_to_html("## Background\nSome text.")
    assert "<h3>Background</h3>" in html
    assert "<p>Some text.</p>" in html
    assert "## Background" not in html


def test_narrative_bullets_render_ul():
    html = _narrative_to_html("- Revenue grew 20%\n- Margins improved\n- New clients won")
    assert "<ul>" in html
    assert "<li>Revenue grew 20%</li>" in html
    assert "<li>Margins improved</li>" in html
    assert "<li>New clients won</li>" in html
    assert "</ul>" in html


def test_narrative_star_bullets_render_ul():
    html = _narrative_to_html("* First point\n* Second point")
    assert "<li>First point</li>" in html
    assert "<li>Second point</li>" in html


def test_narrative_bold_renders_strong():
    html = _narrative_to_html("The **WACC** is derived from first principles.")
    assert "<strong>WACC</strong>" in html
    assert "**WACC**" not in html


def test_narrative_escapes_html_before_inline():
    html = _narrative_to_html("<script>alert(1)</script>\n## <evil> heading\n- <b>item</b>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<evil>" not in html
    assert "&lt;evil&gt;" in html
    assert "<b>item</b>" not in html
    assert "&lt;b&gt;item&lt;/b&gt;" in html


def test_narrative_empty_lines_do_not_produce_paragraphs():
    html = _narrative_to_html("\n\n\n")
    assert "<p>" not in html


def test_narrative_mixed_content():
    text = "## Revenue Model\nThe company sells SaaS.\n\n## Key Metrics\n- ARR: $2.1m\n- NRR: 115%"
    html = _narrative_to_html(text)
    assert "<h3>Revenue Model</h3>" in html
    assert "<p>The company sells SaaS.</p>" in html
    assert "<h3>Key Metrics</h3>" in html
    assert "<li>ARR: $2.1m</li>" in html
    assert "<li>NRR: 115%</li>" in html


def test_disclaimer_section_gets_class():
    html = _render_report_sections_html(
        {"disclaimer": "This report is indicative only."},
        ["disclaimer"],
    )
    assert 'class="report-section disclaimer section-disclaimer"' in html


def test_non_disclaimer_section_no_class():
    html = _render_report_sections_html(
        {"introduction": "Hello."},
        ["introduction"],
    )
    assert "class='disclaimer'" not in html
