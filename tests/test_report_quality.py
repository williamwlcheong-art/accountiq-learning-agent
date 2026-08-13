"""Tests for reusable valuation report quality audits."""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import _e2e_report_content
from main import (
    _render_cover_report_brief_html,
    _render_cover_report_basis_html,
    _render_cover_valuation_snapshot_html,
    _render_report_contents_html,
    _render_report_sections_html,
    _render_valuation_basis_html,
)
from report_prompts import SECTION_SCHEMAS
from report_quality import (
    audit_valuation_pdf_text,
    audit_valuation_report_html,
    audit_valuation_report_content,
    audit_valuation_report_pdf,
)


SAMPLE_PDF_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_sample_valuation_pdf.py"


def _load_sample_pdf_generator():
    spec = importlib.util.spec_from_file_location("generate_sample_valuation_pdf", SAMPLE_PDF_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _otherwise_complete_pdf_text(*, cover_brief: bool = True, demo_mode: bool = True) -> str:
    cover = (
        "PREPARED FOR Example Limited PREPARED BY AccountIQ REPORT TYPE Indicative Valuation Report "
        "REFERENCE AIQ-VAL-000001 VALUATION DATE 4 July 2026 PURPOSE Understand what the business may be worth "
        "BASIS OF VALUE Indicative fair-market value RELIANCE "
    )
    if cover_brief and demo_mode:
        cover += "Demo data only - not for reliance."
    elif cover_brief:
        cover += "Indicative valuation support only; obtain independent professional advice before reliance."
    else:
        cover = ""

    demo_label = "DEMO DATA - NOT FOR RELIANCE" if demo_mode else ""
    return "\n".join(
        [
            demo_label,
            cover,
            "REPORT BASIS",
            "Uploaded financials Revenue, earnings and balance sheet",
            "Five private inputs Only facts management can confirm",
            "Public-source trail Research URLs retained for review",
            "AccountIQ model DCF, WACC, multiples and sensitivity",
            "VALUATION SNAPSHOT",
            "Output High Mid Low",
            "Enterprise value $2,831,000 $2,314,000 $1,898,000",
            "Less: net debt $65,000 $65,000 $65,000",
            "Indicative equity value $2,766,000 $2,249,000 $1,833,000",
            "Contents",
            "Basis of preparation",
            "Report letter",
            "Prepared for Example Limited",
            "Prepared by AccountIQ valuation team",
            "Preparer role Valuation report preparation and evidence synthesis",
            "Organisation AccountIQ",
            "Report channel Secure AccountIQ workspace and downloadable PDF",
            "Purpose and reliance Understand what the business may be worth",
            "Information relied upon uploaded financial statements, five management-confirmed private inputs, the earnings-adjustment review, public-source research and AccountIQ valuation calculations.",
            "Important limitation This is an indicative valuation report only and is not an audit or assurance engagement, legal advice, tax advice, a fairness opinion or a buyer-specific synergy assessment.",
            "Information basis",
            "Prepared from uploaded financial statements, management-confirmed private inputs, public-source research and AccountIQ valuation calculations.",
            "Scope exclusions",
            "Does not constitute an audit, assurance engagement, legal advice, tax advice, transaction fairness opinion or buyer-specific synergy assessment.",
            "Management input trail",
            "Management input - Valuation purpose Management-confirmed private input Frames the report scope, reliance wording and valuation conclusion.",
            "Management input - Owner or key-person dependency Management-confirmed private input Informs continuity, handover risk, transition risk and specific-risk commentary.",
            "Management input - Largest-customer concentration Management-confirmed private input Informs revenue-retention risk, diligence focus and concentration commentary.",
            "Management input - Revenue predictability Management-confirmed private input Informs cash-flow reliability, contract-security commentary and forecast support.",
            "Management input - Revenue outlook Management-confirmed private input Informs the short-term growth assumption or the decision to derive growth from uploaded financial history.",
            "Evidence and model basis",
            "Derived technical assumptions",
            "Discount rate, terminal growth and forecast horizon are derived by the AccountIQ valuation model and disclosed in the report rather than selected by management.",
            "Questions intentionally not asked",
            "Management is not asked to choose the forecast horizon, WACC, terminal growth or discount-rate scenarios.",
            "01 Introduction",
            "02 Executive Summary",
            "03 Overview",
            "04 Market Position",
            "05 About Business Valuations",
            "06 Valuation Methodology Adopted",
            "07 Financial Performance",
            "08 Historical Ratio Analysis",
            "09 Normalisations",
            "10 Balance Sheet Summary",
            "Valuation conclusion at a glance",
            "Enterprise value range $1,898,000 - $2,831,000 Primary DCF valuation range after the private-company illiquidity adjustment.",
            "Midpoint enterprise value $2,314,000 Central indication before the net debt and surplus asset bridge.",
            "Midpoint equity value $2,249,000 Central shareholder-value indication after the enterprise-to-equity bridge.",
            "Net debt adjustment $65,000 Bridge item applied consistently across the valuation scenarios.",
            "Valuation range visual",
            "Low, midpoint and high cases from AccountIQ's valuation schedules.",
            "Mid $2,314,000 Enterprise value Operating-business value before the net-debt bridge. $1,898,000 $2,831,000",
            "Mid $2,249,000 Indicative equity value Shareholder-value range after debt, cash and surplus assets. $1,833,000 $2,766,000",
            "Business context at a glance",
            "Owner or key-person dependency Responsibility is shared across leadership and team Management-supplied context used to frame transition and key-person risk.",
            "Customer concentration 10% to 25% Management-supplied context highlighting whether revenue is exposed to large customers.",
            "Revenue predictability A mix of recurring and one-off revenue Management-supplied context distinguishing recurring, mixed and project-based revenue.",
            "Revenue outlook No specific forecast provided; growth derived from uploaded financial history Management-supplied context used to support or derive the short-term growth assumption.",
            "Market context at a glance",
            "Public sources retained 4 Source URLs are retained for market, profile and benchmark context.",
            "Benchmark evidence Public evidence supports sector or EV/EBITDA context Explains whether public evidence supports market or EV/EBITDA context.",
            "Public profile support Public sources support the company profile or operating context Explains whether public sources support company-profile or operating-context statements.",
            "Comparability caveat Limitations explain the evidence is contextual, not direct pricing Explains that public evidence is used for context and cross-checking, not a direct price.",
            "Methodology at a glance",
            "Primary valuation method Discounted cash flow Forecast free cash flows are the primary valuation basis.",
            "Discount-rate range 9.9% - 13.4% High, midpoint and low WACC scenarios create the valuation range.",
            "Market cross-check 5.0x - 7.0x EV/EBITDA Researched market multiples are used as a reasonableness check.",
            "Equity bridge $2,249,000 Enterprise value is bridged to shareholder value using debt, cash and surplus assets.",
            "Valuation approach selection",
            "Explains why the report adopts DCF, uses market multiples as a cross-check and does not rely on a net-asset method.",
            "Income approach - DCF Adopted as primary Best matches a going-concern SME where value is driven by expected maintainable free cash flow. Primary adjusted enterprise-value range: $1,898,000 - $2,831,000.",
            "Market approach - EV/EBITDA Reasonableness cross-check Useful for market orientation, but not applied mechanically because public and transaction evidence differs in scale, liquidity, growth and participant-specific context. Cross-check range: 5.0x - 7.0x EV/EBITDA.",
            "Asset approach / net assets Not primary The report values the operating business as a going concern rather than on a liquidation or asset-accumulation basis. Balance-sheet inputs are used for the enterprise-to-equity bridge; midpoint equity value is $2,249,000.",
            "Trading performance at a glance",
            "Revenue bridge $980,000 to $1,350,000 Top-line progression across the historical and forecast period shown in the report.",
            "Direct-cost bridge ($392,000) to ($499,500) Shows the cost-of-sales deduction used to move from revenue to gross profit.",
            "Gross profit bridge $588,000 to $850,500 Shows the trading margin available before overheads and other operating expenses.",
            "Operating expense bridge ($423,000) to ($591,500) Shows the overhead deduction used to reconcile gross profit to EBITDA.",
            "EBITDA bridge $165,000 to $259,000 Operating earnings progression before the normalisation schedule is applied.",
            "EBITDA margin bridge 16.8% to 19.2% Shows whether operating leverage is improving, stable or weakening across the period.",
            "Latest actual EBITDA $240,000 Latest actual earnings reference point before forecast and valuation adjustments.",
            "Financial trend visual",
            "Revenue and EBITDA trend from the uploaded-financials schedule.",
            "FY23 Actual $980,000 EBITDA margin 16.8% $165,000",
            "FY24 Actual $1,110,000 EBITDA margin 18.5% $205,000",
            "FY25 Actual $1,250,000 EBITDA margin 19.2% $240,000",
            "FY26 Forecast $1,350,000 EBITDA margin 19.2% $259,000",
            "Margin and growth at a glance",
            "Latest revenue growth 8.0% Latest growth rate shown in the uploaded-financials trend table.",
            "Gross margin bridge 60.0% to 63.0% Shows whether direct-cost efficiency is improving, stable or weakening.",
            "EBITDA margin bridge 16.8% to 19.2% Summarises operating leverage before valuation adjustments.",
            "Net profit margin bridge 10.7% to 12.1% Shows the after-tax profit conversion trend visible in the uploaded financials.",
            "Normalisation impact at a glance",
            "Confirmed adjustments 2 Management-reviewed normalisation items included in the maintainable earnings bridge.",
            "Net EBITDA adjustment $47,000 Net add-back or deduction applied before the valuation earnings base.",
            "Largest adjustment Owner remuneration above market - $35,000 Largest individual normalisation item for adviser or management review.",
            "Normalised EBITDA $287,000 Maintainable earnings base used in the valuation analysis.",
            "Normalised EBITDA bridge",
            "Shows how uploaded operating earnings convert to the maintainable EBITDA used in the valuation.",
            "Uploaded EBITDA basis $240,000 Starting earnings base from the uploaded financial statements.",
            "Net normalisation $47,000 Management-reviewed add-backs or deductions confirmed before valuing maintainable earnings.",
            "Normalised EBITDA $287,000 Maintainable earnings base carried into DCF and market-multiple checks.",
            "Owner review 2 adjustments The earnings bridge comes from the earnings-adjustment review and uploaded accounts.",
            "Source basis Accounts + review The bridge is calculated from uploaded accounts and confirmed adjustment rows.",
            "Valuation use DCF and multiples The same normalised EBITDA is used consistently across valuation methods.",
            "How the discount rate drives the range",
            "High valuation discount rate Lower WACC means forecast cash flows are discounted less heavily, producing the upper valuation case.",
            "Mid valuation discount rate Base discount-rate case used for the central valuation conclusion.",
            "Low valuation discount rate Higher WACC reflects more risk and produces the lower valuation case.",
            "Illiquidity discount Private-company marketability discount shown explicitly rather than hidden in the conclusion.",
            "WACC build visual",
            "Shows the mid-case discount-rate build from public market inputs before the separate illiquidity discount.",
            "Risk-free rate 4.4% Public market base return before company and sector risk.",
            "Beta-adjusted risk premium 7.1% Derived from 1.20 total beta and 5.9% equity risk premium.",
            "Mid WACC 11.5% Discount rate applied to the mid-case forecast cash flows.",
            "Illiquidity discount 11.8% Separate private-company marketability adjustment applied after DCF value.",
            "Source inputs ERP 5.9% / beta 1.20 Public research inputs are disclosed as part of the valuation evidence trail.",
            "Technical inputs Derived WACC, beta and equity-risk-premium assumptions are derived and disclosed as valuation-model inputs.",
            "Enterprise-to-equity bridge",
            "Enterprise-to-equity visual",
            "Shows how operating-business value converts to shareholder value using existing balance-sheet inputs.",
            "Current balance sheet position $370,000 current assets vs $260,000 current liabilities Summarises short-term balance-sheet scale before the valuation bridge.",
            "Total asset and liability base $850,000 total assets vs $420,000 total liabilities Shows the reported balance-sheet base used as context, not as the primary valuation method.",
            "Reported net assets $430,000 Book equity is shown as context and should not be read as the going-concern valuation conclusion.",
            "Midpoint enterprise value $2,314,000 Operating-business value before debt, cash and surplus assets.",
            "Less net debt ($65,000) Interest-bearing debt less available cash.",
            "Surplus assets $0 Separately identified non-operating assets added back.",
            "Midpoint equity value $2,249,000 Indicative shareholder value after the balance-sheet bridge.",
            "How the market cross-check is used",
            "Market multiple range Indicative EV/EBITDA range from researched comparable evidence.",
            "Maintainable EBITDA applied Earnings base used consistently across the market cross-check.",
            "Implied enterprise value range Reasonableness range used to cross-check, not replace, the primary DCF conclusion.",
            "Midpoint market indication Central market-multiple indication before the enterprise-to-equity bridge.",
            "Implied multiple reconciliation",
            "Compares the primary DCF output with the researched EV/EBITDA cross-check range.",
            "Normalised EBITDA $287,000 Maintainable earnings base used for the market and DCF implied multiple checks.",
            "Market EV/EBITDA range 5.0x - 7.0x Researched market range used as a reasonableness cross-check.",
            "DCF post-illiquidity range 6.6x - 9.9x Primary DCF adjusted enterprise-value range expressed as an EV/EBITDA multiple.",
            "DCF pre-illiquidity range 7.5x - 11.2x DCF enterprise-value range before the private-company marketability discount.",
            "DCF midpoint multiple 8.1x Midpoint adjusted DCF enterprise value divided by normalised EBITDA.",
            "Cross-check tension 2.1x above market midpoint Shows whether the selected DCF midpoint sits above or below the market midpoint.",
            "11 Valuation Approach and Assumptions",
            "12 Weighted Average Cost of Capital",
            "Assumption basis at a glance",
            "Maintainable earnings base $287,000 Normalised EBITDA used as the valuation earnings base.",
            "Growth assumption 8.0% Forecast growth assumption disclosed with its source.",
            "Public research inputs 2 Assumptions supported by public market, inflation or discount-rate evidence.",
            "Management-confirmed inputs 5 Management-supplied private inputs used for business-specific assumptions.",
            "Technical model inputs 1 Valuation-model conventions disclosed with the assumption basis.",
            "13 Discounted Cash Flow Analysis",
            "DCF value build visual",
            "Shows how the mid-case discounted cash flows and terminal value convert to adjusted enterprise value.",
            "PV explicit FCFF $836,951 Present value of the five-year forecast cash flows.",
            "PV terminal value $1,787,049 Implied continuing value after the explicit forecast period.",
            "EV before illiquidity $2,624,000 Mid-case DCF enterprise value before the private-company discount.",
            "Illiquidity discount $310,000 Explicit private-company marketability adjustment.",
            "Adjusted enterprise value $2,314,000 Mid-case operating-business value used in the valuation summary.",
            "DCF forecast bridge at a glance",
            "Adjusted enterprise value range $1,898,000 - $2,831,000 DCF valuation range after the private-company illiquidity adjustment.",
            "Midpoint adjusted enterprise value $2,314,000 Central DCF indication before the enterprise-to-equity bridge.",
            "Revenue forecast bridge $1,350,000 to $1,836,660 Mid-case revenue progression across the explicit five-year forecast period.",
            "Free cash flow bridge $198,731 to $270,372 Mid-case free cash flow to firm after tax, capex and working-capital reinvestment.",
            "14 Indicative Valuation Summary",
            "Valuation range at a glance",
            "Primary DCF range $1,898,000 - $2,831,000 Primary enterprise-value range after the private-company illiquidity adjustment.",
            "Midpoint equity value $2,249,000 Central shareholder-value indication after the net-debt bridge.",
            "Market cross-check range $1,370,000 - $1,944,000 Market multiples provide an independent reasonableness check, not the selected conclusion.",
            "DCF vs multiple midpoint $592,000 above Shows where the primary DCF midpoint sits relative to the market cross-check midpoint.",
            "15 Multiples Cross-check",
            "16 Sensitivity and Specific Risks",
            "Sensitivity spread visual",
            "Downside, base and upside adjusted enterprise value from AccountIQ's sensitivity analysis.",
            "Base $2,314,000 Adjusted enterprise value sensitivity Across 6.0% to 10.0% growth and WACC cases.",
            "$1,765,000 $3,054,000",
            "Sensitivity takeaway at a glance",
            "Base sensitivity case $2,314,000 Midpoint case using the base growth assumption and mid WACC scenario.",
            "Quantified EV span $1,765,000 - $3,054,000 Full adjusted enterprise-value span across the WACC and growth matrix.",
            "Growth cases tested 6.0% to 10.0% Growth sensitivity range tested without asking management for extra valuation inputs.",
            "Specific risk factors 5 Qualitative risk factors carried into the report from the short management intake.",
            "17 Comparable Evidence Appendix",
            "18 Sources and References",
            "Comparable evidence at a glance",
            "Evidence rows 3 Public benchmark and context rows retained in the comparable evidence appendix.",
            "Source URLs retained 3 Every evidence row should retain a URL so the reader can check the source trail.",
            "Market multiple support Market evidence supports the EV/EBITDA cross-check Explains whether researched public evidence supports the EV/EBITDA cross-check range.",
            "Comparability caveat Limitations explained as a reasonableness check Explains that public evidence is used for context and cross-checking, not as a direct private-company price.",
            "Source trail at a glance",
            "Public URLs retained 2 Source links are retained so a reader can inspect the public evidence trail.",
            "Discount-rate support Public sources retained for WACC inputs Explains whether public evidence supports the risk-free-rate, equity-risk-premium or beta inputs.",
            "Terminal-growth support Inflation source retained for terminal growth Explains whether public evidence supports inflation or long-term growth assumptions.",
            "Business context support Public profile sources retained for business context Explains whether public sources support company-profile or market-context statements.",
            "19 Disclaimer",
            "Reliance at a glance",
            "Intended use Stated purpose only Reliance is limited to the valuation purpose stated in the report.",
            "Advice status Not advice The report is not a substitute for independent professional advice.",
            "Information reliance Management and public inputs Conclusions depend on management-supplied information, extracted financials and identified sources.",
            "Verification status Not audited The scope is an indicative valuation pack, not an audit or assurance engagement.",
            "Third-party reliance No responsibility accepted Third parties should not rely on the report without their own advice and diligence.",
            "20 General Principles",
            "21 Glossary",
            "01 Introduction",
            "02 Executive Summary",
            "03 Overview",
            "04 Market Position",
            "05 About Business Valuations",
            "06 Valuation Methodology Adopted",
            "07 Financial Performance",
            "08 Historical Ratio Analysis",
            "09 Normalisations",
            "10 Balance Sheet Summary",
            "11 Valuation Approach and Assumptions",
            "12 Weighted Average Cost of Capital",
            "13 Discounted Cash Flow Analysis",
            "14 Indicative Valuation Summary",
            "15 Multiples Cross-check",
            "16 Sensitivity and Specific Risks",
            "17 Comparable Evidence Appendix",
            "Comparable evidence at a glance",
            "Evidence rows 3 Public benchmark and context rows retained in the comparable evidence appendix.",
            "Source URLs retained 3 Every evidence row should retain a URL so the reader can check the source trail.",
            "Market multiple support Market evidence supports the EV/EBITDA cross-check Explains whether researched public evidence supports the EV/EBITDA cross-check range.",
            "Comparability caveat Limitations explained as a reasonableness check Explains that public evidence is used for context and cross-checking, not as a direct private-company price.",
            "Public benchmark evidence is broad sector context, not directly comparable private-company pricing. It is used as a reasonableness cross-check.",
            "18 Sources and References",
            "19 Disclaimer",
            "20 General Principles",
            "21 Glossary",
            "Mid-case forecast cash-flow schedule",
            "Specific risk factors",
            "https://example.com/source-one",
            "https://example.com/source-two",
        ]
    )


def _swap_first_occurrence(text: str, first: str, second: str) -> str:
    placeholder = "__ACCOUNTIQ_SECTION_SWAP_PLACEHOLDER__"
    assert placeholder not in text
    assert first in text
    assert second in text
    return text.replace(first, placeholder, 1).replace(second, first, 1).replace(placeholder, second, 1)


def _current_demo_browser_report_html() -> str:
    sections = _e2e_report_content("valuation_advisory")
    section_order = SECTION_SCHEMAS["valuation_advisory"]
    return "\n".join(
        [
            '<main class="report">',
            '<aside class="demo-banner">Demo data - not for reliance.</aside>',
            '<a class="viewer-download" href="./pdf">Download PDF</a>',
            '<section class="cover">',
            _render_cover_report_basis_html(),
            _render_cover_valuation_snapshot_html(sections),
            "Demo data - not for reliance",
            "Demo Indicative Valuation Report",
            _render_cover_report_brief_html(
                company_name="Browser Quality Limited",
                report_label="Demo Indicative Valuation Report",
                report_id=9001,
                generated_at="2026-07-04 09:30:00",
                valuation_purpose="Understand what the business may be worth",
                demo_mode=True,
            ),
            "</section>",
            '<section class="report-page contents">',
            "<h2>Contents</h2>",
            '<a href="#basis-of-preparation"><span>Front matter</span>Report letter and basis of preparation</a>',
            _render_report_contents_html(sections, section_order),
            "</section>",
            _render_valuation_basis_html(
                company_name="Browser Quality Limited",
                report_label="Demo Indicative Valuation Report",
                report_id=9001,
                demo_mode=True,
                valuation_purpose="Understand what the business may be worth",
                generated_at="2026-07-04 09:30:00",
                intake_answers={
                    "valuation_purpose": "understand_value",
                    "owner_dependency": "shared",
                    "customer_concentration": "10_to_25",
                    "revenue_quality": "mixed",
                    "revenue_outlook": "not_sure",
                },
            ),
            _render_report_sections_html(sections, section_order),
            "</main>",
        ]
    )


def test_valuation_report_content_audit_passes_current_demo_pack():
    audit = audit_valuation_report_content(_e2e_report_content("valuation_advisory"))

    assert audit.passed is True
    assert audit.issues == ()
    assert audit.metadata["section_count"] == 21
    assert audit.metadata["source_url_count"] >= 2


def test_valuation_report_content_audit_requires_complete_cash_flow_schedule_rows():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["dcf_analysis"]["cash_flow_schedule"]["rows"]
    content["dcf_analysis"]["cash_flow_schedule"]["rows"] = [
        row
        for row in rows
        if row[0] not in {"EBITDA", "Discounted free cash flow"}
    ]

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_cash_flow_schedule"
        and "EBITDA" in issue.message
        and "Discounted free cash flow" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_content_audit_rejects_repeated_adjacent_narrative_lines():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["sensitivity_and_risks"]["narrative"] = (
        "## Business-specific matters\n"
        "- Pipeline: unsigned opportunities have not been treated as contracted revenue.\n"
        "- Pipeline: unsigned opportunities have not been treated as contracted revenue.\n"
    )

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert any(
        issue.code == "repeated_narrative_line"
        and "Pipeline: unsigned opportunities" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_content_audit_rejects_revenue_outlook_conflict_before_rendering():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["valuation_assumptions"]["table"]["rows"]
    growth_row = next(row for row in rows if row[0] == "Revenue and earnings growth")
    growth_row[2] = "Management outlook: modest growth"
    risk_rows = content["sensitivity_and_risks"]["specific_risk_factors"]["rows"]
    outlook_row = next(row for row in risk_rows if row[0] == "Revenue outlook and pipeline")
    outlook_row[1] = "Modest growth"
    outlook_row[3] = "Modest growth supports the base forecast, subject to delivery and customer retention."

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert any(
        issue.code == "content_revenue_outlook_inconsistency"
        and "management outlook: modest growth" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_passes_current_demo_browser_pack():
    audit = audit_valuation_report_html(_current_demo_browser_report_html(), demo_mode=True)

    assert audit.passed is True
    assert audit.issues == ()
    assert audit.metadata["url_count"] >= 2


def test_valuation_report_html_audit_requires_cover_valuation_snapshot():
    sections = _e2e_report_content("valuation_advisory")
    html = _current_demo_browser_report_html().replace(
        _render_cover_valuation_snapshot_html(sections),
        "",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "missing_html_cover_snapshot" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_requires_cover_report_basis_strip():
    html = _current_demo_browser_report_html().replace(_render_cover_report_basis_html(), "")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "missing_html_cover_report_basis" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_requires_cover_valuation_snapshot_detail():
    html = _current_demo_browser_report_html()
    old = (
        "<tbody><tr><td>Enterprise value</td><td>$2,831,000</td><td>$2,314,000</td><td>$1,898,000</td></tr>"
        "<tr><td>Less: net debt</td><td>$65,000</td><td>$65,000</td><td>$65,000</td></tr>"
        "<tr><td>Indicative equity value</td><td>$2,766,000</td><td>$2,249,000</td><td>$1,833,000</td></tr></tbody>"
    )
    assert old in html
    html = html.replace(old, "<tbody><tr><td>Summary values shown later in the report</td></tr></tbody>")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_cover_snapshot"
        and "Enterprise value" in issue.message
        and "Net debt" in issue.message
        and "Indicative equity value" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_cover_net_debt_bridge():
    html = _current_demo_browser_report_html()
    old = "<tr><td>Less: net debt</td><td>$65,000</td><td>$65,000</td><td>$65,000</td></tr>"
    assert old in html
    html = html.replace(old, "")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_cover_snapshot"
        and "Net debt" in issue.message
        and "Enterprise value" not in issue.message
        and "Indicative equity value" not in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_cover_snapshot_values():
    html = _current_demo_browser_report_html()
    for value in (
        "$2,831,000",
        "$2,314,000",
        "$1,898,000",
        "$65,000",
        "$2,766,000",
        "$2,249,000",
        "$1,833,000",
    ):
        html = html.replace(value, "Value not shown")
    html = html.replace(
        "<p class=\"company\">AccountIQ Sample Limited</p>",
        "<p class=\"company\">AccountIQ Sample Limited</p><p>Unrelated cover values: $1 $2 $3 $4 $5 $6 $7 $8 $9</p>",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "thin_html_cover_snapshot_values"
        and "Found 0 dollar values" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_complete_high_mid_low_cover_snapshot_values():
    html = _current_demo_browser_report_html()
    html = html.replace("<td>$65,000</td><td>$65,000</td><td>$65,000</td>", "<td>$65,000</td><td>Not shown</td><td>Not shown</td>")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "thin_html_cover_snapshot_values"
        and "Found 7 dollar values" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_values_on_each_cover_snapshot_row():
    html = _current_demo_browser_report_html()
    html = html.replace(
        "<tr><td>Less: net debt</td><td>$65,000</td><td>$65,000</td><td>$65,000</td></tr>",
        "<tr><td>Extra valuation values</td><td>$65,000</td><td>$65,000</td><td>$65,000</td></tr>"
        "<tr><td>Less: net debt</td><td>Not shown</td><td>Not shown</td><td>Not shown</td></tr>",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_cover_snapshot_rows"
        and "Net debt: 0 dollar values" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_professional_cover_brief():
    html = _current_demo_browser_report_html().replace(
        "<dt>Prepared for</dt>",
        "<dt>Client</dt>",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_cover_marker"
        and "Prepared for" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_safe_clickable_source_links():
    html = _current_demo_browser_report_html().replace(
        ' target="_blank" rel="noopener noreferrer"',
        "",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert audit.metadata["url_count"] >= 2
    assert "html_source_links_not_clickable" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_requires_source_support_descriptions():
    html = _current_demo_browser_report_html()
    source_row = (
        '<tr><td>NZ Companies Office</td><td><a href="https://companies-register.companiesoffice.govt.nz/" '
        'target="_blank" rel="noopener noreferrer">https://companies-register.companiesoffice.govt.nz/</a></td>'
        "<td>Company public-profile corroboration</td></tr>"
    )
    thin_row = (
        '<tr><td>Thin source</td><td><a href="https://example.com/thin-source" '
        'target="_blank" rel="noopener noreferrer">https://example.com/thin-source</a></td>'
        "<td>Website</td></tr>"
    )
    assert source_row in html
    html = html.replace(source_row, thin_row)

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_source_rows_thin_support"
        and "thin-source" in issue.message
        and "Website" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_catches_unicode_dash_layout_artifacts():
    html = _current_demo_browser_report_html()
    html += "<p>Revenue growth \u2011 EBITDA margin \u2212 WACC spread.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_layout_artifact"
        and "\u2011" in issue.message
        and "\u2212" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_catches_missing_front_matter_and_unsafe_markup():
    html = _current_demo_browser_report_html()
    html = html.replace('id="basis-of-preparation"', 'id="missing-basis"')
    html = html.replace("Management input trail", "Removed trail")
    for marker in (
        "Management input - Valuation purpose",
        "Management input - Owner or key-person dependency",
        "Management input - Largest-customer concentration",
        "Management input - Revenue predictability",
        "Management input - Revenue outlook",
    ):
        html = html.replace(marker, "Management input removed")
    html += '<script>alert("x")</script>'

    audit = audit_valuation_report_html(html, demo_mode=True)
    codes = {issue.code for issue in audit.issues}

    assert audit.passed is False
    assert "missing_html_basis_page" in codes
    assert "missing_html_management_input_trail" in codes
    assert "html_script_tag" in codes


def test_valuation_report_html_audit_requires_management_input_rationale():
    html = _current_demo_browser_report_html().replace(
        "Informs continuity, handover risk, transition risk and specific-risk commentary.",
        "Used as general owner context.",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_management_input_trail_detail"
        and "Owner or key-person dependency" in issue.message
        and "transition risk" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_separated_front_matter_blocks():
    html = _current_demo_browser_report_html().replace(
        "<h3>Management input trail</h3>",
        "",
    ).replace(
        "<h3>Evidence and model basis</h3>",
        "<h3>Management input trail</h3><h3>Evidence and model basis</h3>",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_front_matter_structure"
        and "Management input - Valuation purpose" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_visible_source_hierarchy():
    html = _current_demo_browser_report_html().replace(
        "AccountIQ valuation calculations",
        "internal calculations",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_source_hierarchy"
        and "AccountIQ valuation calculations" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_rejects_customer_visible_builder_language():
    html = _current_demo_browser_report_html().replace(
        "Low, midpoint and high cases from AccountIQ&#x27;s valuation schedules.",
        "Low, midpoint and high cases sourced from AccountIQ-computed valuation rows.",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_implementation_language"
        and "computed valuation rows" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_rejects_raw_internal_valuation_source_keys():
    html = _current_demo_browser_report_html() + (
        "<p>Growth source: management_custom_override and working capital source: "
        "extracted_operating_line_items.</p>"
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_internal_valuation_key_language"
        and "management_custom_override" in issue.message
        and "extracted_operating_line_items" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_rejects_raw_intake_field_and_option_keys():
    html = _current_demo_browser_report_html() + (
        "<p>Raw intake leaked: customer_concentration=10_to_25 and "
        "revenue_outlook=not_sure.</p>"
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_raw_valuation_intake_key_language"
        and "customer_concentration" in issue.message
        and "10_to_25" in issue.message
        and "not_sure" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_rejects_revenue_outlook_conflict_after_not_sure():
    html = _current_demo_browser_report_html() + (
        "\n<section><h3>Business context at a glance</h3>"
        "<dl><dt>Revenue outlook</dt><dd>Modest growth</dd></dl></section>"
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_revenue_outlook_inconsistency"
        and "revenue outlook modest growth" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_rejects_repeated_adjacent_narrative_sentences():
    repeated = "Customer retention should be reviewed before any reliance decision."
    html = _current_demo_browser_report_html() + f"<p>{repeated}</p><p>{repeated}</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_repeated_narrative_sentence"
        and "Customer retention should be reviewed" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_derived_technical_assumptions_marker():
    html = _current_demo_browser_report_html().replace(
        "Derived technical assumptions",
        "Technical assumptions",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_marker"
        and "Derived technical assumptions" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_derived_technical_assumptions_detail():
    html = (
        _current_demo_browser_report_html()
        .replace("Discount rate, terminal growth and forecast horizon", "technical assumptions")
        .replace("forecast horizon, WACC, terminal growth or discount-rate scenarios", "technical inputs")
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_derived_technical_assumption_detail"
        and "terminal growth" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_intentionally_not_asked_marker():
    html = _current_demo_browser_report_html().replace(
        "Questions intentionally not asked",
        "Avoided technical inputs",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_marker"
        and "Questions intentionally not asked" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_report_letter_marker():
    html = _current_demo_browser_report_html().replace(
        "Report letter",
        "Engagement note",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_marker"
        and "Report letter" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_all_numbered_sections():
    html = _current_demo_browser_report_html().replace(
        '<span class="section-number">15</span> Multiples Cross-check',
        '<span class="section-number">15</span> Market Cross-check',
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_numbered_section_mismatch"
        and "15 Multiples Cross-check" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_numbered_section_order():
    html = _swap_first_occurrence(
        _current_demo_browser_report_html(),
        "<span class='contents-number'>14</span><span>Indicative Valuation Summary</span>",
        "<span class='contents-number'>15</span><span>Multiples Cross-check</span>",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "html_numbered_section_order"
        and "15 Multiples Cross-check" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_scope_exclusion_detail():
    html = _current_demo_browser_report_html().replace(
        "buyer-specific synergy assessment",
        "transaction-specific assessment",
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_scope_exclusions"
        and "buyer-specific synergy assessment" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_comparable_caveat():
    html = _current_demo_browser_report_html()
    replacements = {
        (
            "It is broad-sector evidence rather than a set of directly comparable private "
            "transactions, so the observed range is used only as a reasonableness check."
        ): "The evidence directly prices the subject business.",
        "Broad listed-company evidence; larger and more liquid than the subject": (
            "Direct private-company pricing evidence"
        ),
        "Limitations explained as a reasonableness check": (
            "No limitation noted"
        ),
        "Explains that public evidence is used for context and cross-checking, not as a direct private-company price.": (
            "Summarises the evidence."
        ),
    }
    for old, new in replacements.items():
        assert old in html
        html = html.replace(old, new)

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_html_comparable_caveat"
        and "not-directly-comparable limitation" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_interpretation_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Reasonableness range used to cross-check, not replace, the primary DCF conclusion."
    assert old in html
    html = html.replace(old, "Market range shown beside the DCF output.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_interpretation_panels"
        and "How the market cross-check is used" in issue.message
        and "reasonableness not primary conclusion" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_executive_conclusion_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Central shareholder-value indication after the enterprise-to-equity bridge."
    assert old in html
    html = html.replace(old, "Central indication shown in the table.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Valuation conclusion at a glance" in issue.message
        and "midpoint equity value" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_methodology_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Forecast free cash flows are the primary valuation basis."
    assert old in html
    html = html.replace(old, "DCF is selected for this report.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Methodology at a glance" in issue.message
        and "primary DCF method" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_trading_performance_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Operating earnings progression before the normalisation schedule is applied."
    assert old in html
    html = html.replace(old, "Operating earnings shown in this row.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Trading performance at a glance" in issue.message
        and "EBITDA bridge before normalisation" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_margin_growth_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Shows whether direct-cost efficiency is improving, stable or weakening."
    assert old in html
    html = html.replace(old, "Gross margin row shown.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Margin and growth at a glance" in issue.message
        and "gross margin bridge" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_normalisation_impact_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Management-reviewed normalisation items included in the maintainable earnings bridge."
    assert old in html
    html = html.replace(old, "Normalisation items shown.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Normalisation impact at a glance" in issue.message
        and "confirmed adjustment count" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_business_context_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Management-supplied context highlighting whether revenue is exposed to large customers."
    assert old in html
    html = html.replace(old, "Management context shown for this answer.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Business context at a glance" in issue.message
        and "customer-concentration context" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_market_context_glance_panel_detail():
    html = _current_demo_browser_report_html()
    replacements = {
        "Limitations explain the evidence is contextual, not direct pricing": "Public evidence included",
        "Explains that public evidence is used for context and cross-checking, not a direct price.": (
            "Signals that public evidence is included."
        ),
    }
    for old, new in replacements.items():
        assert old in html
        html = html.replace(old, new)

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Market context at a glance" in issue.message
        and "comparability caveat" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_assumption_basis_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Management-supplied private inputs used for business-specific assumptions."
    assert old in html
    html = html.replace(old, "Management inputs are shown.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Assumption basis at a glance" in issue.message
        and "management-confirmed source mix" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_dcf_forecast_bridge_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Mid-case free cash flow to firm after tax, capex and working-capital reinvestment."
    assert old in html
    html = html.replace(old, "Mid-case cash flow shown.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "DCF forecast bridge at a glance" in issue.message
        and "free-cash-flow bridge" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_valuation_range_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Market multiples provide an independent reasonableness check, not the selected conclusion."
    assert old in html
    html = html.replace(old, "Market multiple range shown for comparison.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Valuation range at a glance" in issue.message
        and "market cross-check range" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_sensitivity_takeaway_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "Growth sensitivity range tested without asking management for extra valuation inputs."
    assert old in html
    html = html.replace(old, "Growth sensitivity range shown.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Sensitivity takeaway at a glance" in issue.message
        and "growth cases without extra questions" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_comparable_evidence_glance_panel_detail():
    html = _current_demo_browser_report_html()
    replacements = {
        "Limitations explained as a reasonableness check": "Evidence retained",
        "Explains that public evidence is used for context and cross-checking, not as a direct private-company price.": (
            "Comparable evidence shown."
        ),
    }
    for old, new in replacements.items():
        assert old in html
        html = html.replace(old, new)

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Comparable evidence at a glance" in issue.message
        and "comparability caveat" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_range_visual_detail():
    html = _current_demo_browser_report_html()
    old = "Operating-business value before the net-debt bridge."
    assert old in html
    html = html.replace(old, "Operating-business value shown in the chart.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_visual_panels"
        and "Valuation range visual" in issue.message
        and "enterprise-value visual row" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_dcf_value_build_visual_detail():
    html = _current_demo_browser_report_html()
    old = "Implied continuing value after the explicit forecast period."
    assert old in html
    html = html.replace(old, "Terminal component shown in the chart.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_visual_panels"
        and "DCF value build visual" in issue.message
        and "terminal-value PV" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_wacc_build_visual_detail():
    html = _current_demo_browser_report_html()
    old = "Derived from 1.20 total beta and 5.9% equity risk premium."
    assert old in html
    html = html.replace(old, "Derived from public market evidence.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_visual_panels"
        and "WACC build visual" in issue.message
        and "beta-adjusted premium input" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_enterprise_to_equity_visual_detail():
    html = _current_demo_browser_report_html()
    old = "Interest-bearing debt less available cash."
    assert old in html
    html = html.replace(old, "Bridge adjustment shown in the chart.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_visual_panels"
        and "Enterprise-to-equity visual" in issue.message
        and "net-debt bridge adjustment" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_normalised_ebitda_bridge_detail():
    html = _current_demo_browser_report_html()
    old = "Management-reviewed add-backs or deductions confirmed before valuing maintainable earnings."
    assert old in html
    html = html.replace(old, "Adjustment effect shown in the chart.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_visual_panels"
        and "Normalised EBITDA bridge" in issue.message
        and "net-normalisation adjustment" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_sensitivity_spread_visual_detail():
    html = _current_demo_browser_report_html()
    old = "Across 6.0% to 10.0% growth and WACC cases."
    assert old in html
    html = html.replace(old, "Across tested assumptions.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_visual_panels"
        and "Sensitivity spread visual" in issue.message
        and "growth-and-WACC case range" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_financial_trend_visual_detail():
    html = _current_demo_browser_report_html()
    old = "Revenue and EBITDA trend from the uploaded-financials schedule."
    assert old in html
    html = html.replace(old, "Financial trend shown from available accounts.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_visual_panels"
        and "Financial trend visual" in issue.message
        and "uploaded-financials premise" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_valuation_approach_selection_detail():
    html = _current_demo_browser_report_html()
    old = "Best matches a going-concern SME where value is driven by expected maintainable free cash flow."
    assert old in html
    html = html.replace(old, "Selected as the main approach.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_visual_panels"
        and "Valuation approach selection" in issue.message
        and "income approach adopted as primary" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_implied_multiple_reconciliation_detail():
    html = _current_demo_browser_report_html()
    old = "Primary DCF adjusted enterprise-value range expressed as an EV/EBITDA multiple."
    assert old in html
    html = html.replace(old, "DCF multiple range shown for comparison.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_visual_panels"
        and "Implied multiple reconciliation" in issue.message
        and "DCF post-illiquidity range" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_source_glance_panel_detail():
    html = _current_demo_browser_report_html()
    replacements = {
        "Discount-rate support": "Rate support",
        "Public sources retained for WACC inputs": "WACC sources retained",
        "Explains whether public evidence supports the risk-free-rate, equity-risk-premium or beta inputs.": (
            "Shows whether sources are available."
        ),
    }
    for old, new in replacements.items():
        assert old in html
        html = html.replace(old, new)

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Source trail at a glance" in issue.message
        and "discount-rate source support" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_requires_reliance_glance_panel_detail():
    html = _current_demo_browser_report_html()
    old = "The report is not a substitute for independent professional advice."
    assert old in html
    html = html.replace(old, "Read the full disclaimer before relying on the report.")

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_html_glance_panels"
        and "Reliance at a glance" in issue.message
        and "advice-status limit" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_html_audit_rejects_non_public_source_urls():
    html = _current_demo_browser_report_html()
    sources_start = html.index('id="sources"')
    sources_end = html.index("</section>", sources_start)
    html = (
        html[:sources_end]
        + '<p>Internal source http://127.0.0.1/internal</p>'
        + html[sources_end:]
    )

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert audit.metadata["non_public_source_url_count"] == 1
    assert "html_non_public_source_urls" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_requires_demo_or_live_reliance_context():
    html = _current_demo_browser_report_html().replace(
        "Demo data - not for reliance",
        "Confidential indicative report",
    ).replace(
        "Demo data only - not for reliance.",
        "Confidential indicative report.",
    )

    demo_audit = audit_valuation_report_html(html, demo_mode=True)
    live_audit = audit_valuation_report_html(html, demo_mode=False)

    assert "missing_html_demo_label" in {issue.code for issue in demo_audit.issues}
    assert "missing_html_live_cover_reliance" in {issue.code for issue in live_audit.issues}


def test_valuation_report_html_audit_rejects_demo_language_in_live_report():
    html = (
        _current_demo_browser_report_html()
        .replace("Demo data - not for reliance", "Confidential - indicative only")
        .replace(
            "Demo data only - not for reliance.",
            "Indicative valuation support only; obtain independent professional advice before reliance.",
        )
        + "<p>The sample company summary should not appear in a live report.</p>"
    )

    audit = audit_valuation_report_html(html, demo_mode=False)

    assert audit.passed is False
    assert "html_demo_language_in_live_report" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_source_and_internal_language_gaps():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " OpenAI returned this JSON object. Growth source management_custom_override. "
        "Raw answer revenue_outlook=not_sure."
    )
    content["sources"]["table"]["rows"] = [["Source name only", "", "No URL"]]
    content["comparable_evidence"]["table"]["rows"] = [
        ["Comparable deal", "2025", "5.0x", "No source URL", "Source name only"]
    ]

    audit = audit_valuation_report_content(content)
    codes = {issue.code for issue in audit.issues}

    assert audit.passed is False
    assert "implementation_language" in codes
    assert "internal_valuation_key_language" in codes
    assert "raw_valuation_intake_key_language" in codes
    assert "thin_source_trail" in codes
    assert "missing_comparable_urls" in codes


def test_valuation_report_content_audit_requires_url_in_each_comparable_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    rows = content["comparable_evidence"]["table"]["rows"]
    rows.append(["Unsupported comparable", "2025", "5.0x", "Broad reference", "No URL in this row"])

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert audit.metadata["comparable_url_count"] >= 1
    assert audit.metadata["comparable_rows_missing_url_count"] == 1
    assert any(
        issue.code == "comparable_rows_missing_urls"
        and "Missing rows" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_content_audit_requires_comparable_caveat():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["comparable_evidence"]["narrative"] = (
        "The public evidence directly prices the subject business."
    )
    for row in content["comparable_evidence"]["table"]["rows"]:
        row[3] = "Direct private-company pricing evidence."

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "not-directly-comparable limitation" in audit.metadata["comparable_caveat_missing"]
    assert any(
        issue.code == "missing_comparable_caveat"
        and "not direct private-company pricing" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_content_audit_requires_url_in_each_source_row():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["sources"]["table"]["rows"].append(["Unsupported source", "", "No URL in this row"])

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert audit.metadata["source_url_count"] >= 2
    assert audit.metadata["source_rows_missing_url_count"] == 1
    assert any(
        issue.code == "source_rows_missing_urls"
        and "Missing rows" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_content_audit_requires_source_support_descriptions():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["sources"]["table"]["rows"].append(
        ["Generic source", "https://example.com/generic-source", "Website"]
    )

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert audit.metadata["source_rows_missing_url_count"] == 0
    assert audit.metadata["source_rows_thin_support_count"] == 1
    assert any(
        issue.code == "source_rows_thin_support"
        and "Thin rows" in issue.message
        for issue in audit.issues
    )


def test_valuation_report_content_audit_rejects_non_public_source_urls():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["sources"]["table"]["rows"].append(
        [
            "Internal source",
            "http://192.168.1.20/internal",
            "Supports business-context corroboration.",
        ]
    )

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert audit.metadata["non_public_source_url_count"] == 1
    assert "non_public_source_urls" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_unfinished_follow_up_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " Please provide additional information before this report can be completed."
    )

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_adviser_follow_up_instruction():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " Ask your accountant to provide more information before relying on this report."
    )

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_management_follow_up_instruction():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " Management should provide customer contracts before this valuation can be finalised."
    )

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_follow_up_item_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " Customer concentration analysis remains a follow-up item."
    )

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_template_placeholder_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["market_position"]["narrative"] += "\n\nMarket evidence to be confirmed."

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "placeholder_text" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_draft_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["executive_summary"]["narrative"] += (
        " This is a first draft valuation report for management review."
    )

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "draft_language" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_legacy_owner_dependency_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["business_overview"] += "\n\nOwner dependency remains a specific diligence issue."

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "legacy_owner_dependency_language" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_legacy_private_context_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    content["business_overview"] += "\n\nPrivate buyer context: A key contract renews next year."

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "legacy_private_context_language" in {issue.code for issue in audit.issues}


def test_valuation_report_content_audit_catches_sale_process_risk_language():
    content = copy.deepcopy(_e2e_report_content("valuation_advisory"))
    risk_rows = content["sensitivity_and_risks"]["specific_risk_factors"]["rows"]
    risk_rows[0][2] = "Affects buyer confidence in post-transaction continuity."
    content["normalisations_schedule"]["narrative"] += "\n\nLargest adjustment is for adviser or buyer review."
    content["valuation_methodology"] += "\n\nMarket evidence differs by buyer context."

    audit = audit_valuation_report_content(content)

    assert audit.passed is False
    assert "sale_process_risk_language" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_catches_unfinished_follow_up_language():
    html = _current_demo_browser_report_html()
    html += "<p>Please upload a detailed customer list before this report can be completed.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "html_unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_catches_more_document_instruction():
    html = _current_demo_browser_report_html()
    html += "<p>Upload additional documents so the valuation can be finalised.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "html_unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_catches_user_follow_up_instruction():
    html = _current_demo_browser_report_html()
    html += "<p>The user should provide signed contracts before the valuation is relied on.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "html_unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_catches_follow_up_item_language():
    html = _current_demo_browser_report_html()
    html += "<p>Customer concentration analysis remains a follow-up item.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "html_unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_catches_template_placeholder_language():
    html = _current_demo_browser_report_html()
    html += "<p>Market evidence TBD.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "html_placeholder_text" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_catches_draft_language():
    html = _current_demo_browser_report_html()
    html += "<p>This is a working draft valuation pack.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "html_draft_language" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_catches_legacy_owner_dependency_language():
    html = _current_demo_browser_report_html()
    html += "<p>Management input - Owner dependency informs buyer reliance on the owner.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "html_legacy_owner_dependency_language" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_catches_legacy_private_context_language():
    html = _current_demo_browser_report_html()
    html += "<p>Optional buyer context was supplied for the valuation.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "html_legacy_private_context_language" in {issue.code for issue in audit.issues}


def test_valuation_report_html_audit_catches_sale_process_risk_language():
    html = _current_demo_browser_report_html()
    html += "<p>The largest adjustment is for adviser or buyer review and buyer context.</p>"

    audit = audit_valuation_report_html(html, demo_mode=True)

    assert audit.passed is False
    assert "html_sale_process_risk_language" in {issue.code for issue in audit.issues}


def test_valuation_pdf_audit_passes_current_sample_pdf(tmp_path):
    generator = _load_sample_pdf_generator()
    output_path = generator.generate_sample_pdf(tmp_path / "sample.pdf")

    audit = audit_valuation_report_pdf(output_path, demo_mode=True)

    assert audit.passed is True
    assert audit.issues == ()
    assert audit.metadata["page_count"] >= 20
    assert audit.metadata["url_count"] >= 2
    assert audit.metadata["demo_labelled_page_count"] == audit.metadata["page_count"]


def test_valuation_pdf_audit_requires_demo_label_on_every_page(tmp_path, monkeypatch):
    import pdfplumber

    pdf_path = tmp_path / "partly-labelled-demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% mocked pdf\n")

    class FakePage:
        def __init__(self, text: str):
            self._text = text

        def extract_text(self):
            return self._text

    class FakePdf:
        def __init__(self, page_texts: list[str]):
            self.pages = [FakePage(text) for text in page_texts]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    page_texts = [_otherwise_complete_pdf_text()]
    page_texts.extend(
        f"DEMO DATA - NOT FOR RELIANCE supporting page {index}"
        for index in range(2, 25)
    )
    page_texts.append("Unlabelled appendix page")
    monkeypatch.setattr(pdfplumber, "open", lambda _path: FakePdf(page_texts))

    audit = audit_valuation_report_pdf(pdf_path, demo_mode=True)

    assert audit.passed is False
    assert audit.metadata["page_count"] == 25
    assert audit.metadata["demo_labelled_page_count"] == 24
    assert any(
        issue.code == "missing_demo_label_pages"
        and "25" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_catches_thin_pack_and_demo_mismatch():
    text = "Indicative Valuation Report\n01 Introduction\n21 Glossary\nhttps://example.com"

    audit = audit_valuation_pdf_text(text, page_count=3, demo_mode=True)
    codes = {issue.code for issue in audit.issues}

    assert audit.passed is False
    assert "thin_pdf_page_count" in codes
    assert "missing_demo_label" in codes
    assert "pdf_thin_source_trail" in codes
    assert "missing_pdf_marker" in codes


def test_valuation_pdf_text_audit_requires_source_support_descriptions():
    text = _otherwise_complete_pdf_text()
    thin_row = "\nhttps://example.com/thin-source Website\n"
    head, marker, tail = text.rpartition("19 Disclaimer")
    text = f"{head}{thin_row}{marker}{tail}"

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_source_rows_thin_support"
        and "thin-source" in issue.message
        and "Website" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_catches_unicode_dash_layout_artifacts():
    text = _otherwise_complete_pdf_text() + "\nRevenue growth \u2011 EBITDA margin \u2212 WACC spread."

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_layout_artifact"
        and "\u2011" in issue.message
        and "\u2212" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_rejects_customer_visible_builder_language():
    text = (
        _otherwise_complete_pdf_text()
        + "\nDownside, base and upside adjusted enterprise value from the computed sensitivity matrix."
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_implementation_language"
        and "computed sensitivity matrix" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_rejects_raw_internal_valuation_source_keys():
    text = (
        _otherwise_complete_pdf_text()
        + "\nGrowth source: historical_revenue_cagr_capped; working capital source: extracted_current_totals."
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_internal_valuation_key_language"
        and "historical_revenue_cagr_capped" in issue.message
        and "extracted_current_totals" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_rejects_raw_intake_field_and_option_keys():
    text = (
        _otherwise_complete_pdf_text()
        + "\nRaw intake leaked: valuation_purpose=sale_or_transaction; revenue_quality=mostly_one_off."
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_raw_valuation_intake_key_language"
        and "valuation_purpose" in issue.message
        and "sale_or_transaction" in issue.message
        and "mostly_one_off" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_rejects_revenue_outlook_conflict_after_not_sure():
    text = (
        _otherwise_complete_pdf_text()
        + "\nManagement input - Revenue outlook Management-confirmed private input No specific forecast provided; growth derived from uploaded financial history."
        + "\nRevenue outlook and pipeline Modest growth"
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_revenue_outlook_inconsistency"
        and "revenue outlook and pipeline modest growth" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_rejects_repeated_adjacent_narrative_sentences():
    repeated = (
        "Customer retention should be reviewed before any reliance decision because "
        "forecast cash flows depend on repeat purchasing."
    )
    text = _otherwise_complete_pdf_text() + f"\n{repeated}\n{repeated}"

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_repeated_narrative_sentence"
        and "Customer retention should be reviewed" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_interpretation_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Lower WACC means forecast cash flows are discounted less heavily, producing the upper valuation case.",
        "High valuation case shown.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_interpretation_panels"
        and "How the discount rate drives the range" in issue.message
        and "lower WACC upper-valuation link" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_executive_conclusion_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Central shareholder-value indication after the enterprise-to-equity bridge.",
        "Central indication shown in the table.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Valuation conclusion at a glance" in issue.message
        and "midpoint equity value" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_methodology_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Forecast free cash flows are the primary valuation basis.",
        "DCF is selected for this report.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Methodology at a glance" in issue.message
        and "primary DCF method" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_trading_performance_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Operating earnings progression before the normalisation schedule is applied.",
        "Operating earnings shown in this row.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Trading performance at a glance" in issue.message
        and "EBITDA bridge before normalisation" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_margin_growth_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Shows whether direct-cost efficiency is improving, stable or weakening.",
        "Gross margin row shown.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Margin and growth at a glance" in issue.message
        and "gross margin bridge" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_normalisation_impact_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Management-reviewed normalisation items included in the maintainable earnings bridge.",
        "Normalisation items shown.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Normalisation impact at a glance" in issue.message
        and "confirmed adjustment count" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_business_context_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Management-supplied context highlighting whether revenue is exposed to large customers.",
        "Management context shown for this answer.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Business context at a glance" in issue.message
        and "customer-concentration context" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_market_context_glance_panel_detail():
    text = _otherwise_complete_pdf_text()
    replacements = {
        "Limitations explain the evidence is contextual, not direct pricing": "Public evidence included",
        "Explains that public evidence is used for context and cross-checking, not a direct price.": (
            "Signals that public evidence is included."
        ),
    }
    for old, new in replacements.items():
        assert old in text
        text = text.replace(old, new)

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Market context at a glance" in issue.message
        and "comparability caveat" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_assumption_basis_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Management-supplied private inputs used for business-specific assumptions.",
        "Management inputs are shown.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Assumption basis at a glance" in issue.message
        and "management-confirmed source mix" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_dcf_forecast_bridge_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Mid-case free cash flow to firm after tax, capex and working-capital reinvestment.",
        "Mid-case cash flow shown.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "DCF forecast bridge at a glance" in issue.message
        and "free-cash-flow bridge" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_valuation_range_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Market multiples provide an independent reasonableness check, not the selected conclusion.",
        "Market multiple range shown for comparison.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Valuation range at a glance" in issue.message
        and "market cross-check range" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_sensitivity_takeaway_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Growth sensitivity range tested without asking management for extra valuation inputs.",
        "Growth sensitivity range shown.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Sensitivity takeaway at a glance" in issue.message
        and "growth cases without extra questions" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_comparable_evidence_glance_panel_detail():
    text = _otherwise_complete_pdf_text()
    replacements = {
        "Limitations explained as a reasonableness check": "Evidence retained",
        "Explains that public evidence is used for context and cross-checking, not as a direct private-company price.": (
            "Comparable evidence shown."
        ),
    }
    for old, new in replacements.items():
        assert old in text
        text = text.replace(old, new)

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Comparable evidence at a glance" in issue.message
        and "comparability caveat" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_range_visual_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Operating-business value before the net-debt bridge.",
        "Operating-business value shown in the chart.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_visual_panels"
        and "Valuation range visual" in issue.message
        and "enterprise-value visual row" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_dcf_value_build_visual_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Implied continuing value after the explicit forecast period.",
        "Terminal component shown in the chart.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_visual_panels"
        and "DCF value build visual" in issue.message
        and "terminal-value PV" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_wacc_build_visual_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Derived from 1.20 total beta and 5.9% equity risk premium.",
        "Derived from public market evidence.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_visual_panels"
        and "WACC build visual" in issue.message
        and "beta-adjusted premium input" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_enterprise_to_equity_visual_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Interest-bearing debt less available cash.",
        "Bridge adjustment shown in the chart.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_visual_panels"
        and "Enterprise-to-equity visual" in issue.message
        and "net-debt bridge adjustment" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_normalised_ebitda_bridge_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Management-reviewed add-backs or deductions confirmed before valuing maintainable earnings.",
        "Adjustment effect shown in the chart.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_visual_panels"
        and "Normalised EBITDA bridge" in issue.message
        and "net-normalisation adjustment" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_sensitivity_spread_visual_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Across 6.0% to 10.0% growth and WACC cases.",
        "Across tested assumptions.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_visual_panels"
        and "Sensitivity spread visual" in issue.message
        and "growth-and-WACC case range" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_financial_trend_visual_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Revenue and EBITDA trend from the uploaded-financials schedule.",
        "Financial trend shown from available accounts.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_visual_panels"
        and "Financial trend visual" in issue.message
        and "uploaded-financials premise" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_valuation_approach_selection_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Best matches a going-concern SME where value is driven by expected maintainable free cash flow.",
        "Selected as the main approach.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_visual_panels"
        and "Valuation approach selection" in issue.message
        and "income approach adopted as primary" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_implied_multiple_reconciliation_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Primary DCF adjusted enterprise-value range expressed as an EV/EBITDA multiple.",
        "DCF multiple range shown for comparison.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_visual_panels"
        and "Implied multiple reconciliation" in issue.message
        and "DCF post-illiquidity range" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_source_glance_panel_detail():
    text = _otherwise_complete_pdf_text()
    replacements = {
        "Discount-rate support": "Rate support",
        "Public sources retained for WACC inputs": "WACC sources retained",
        "Explains whether public evidence supports the risk-free-rate, equity-risk-premium or beta inputs.": (
            "Shows whether sources are available."
        ),
    }
    for old, new in replacements.items():
        assert old in text
        text = text.replace(old, new)

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Source trail at a glance" in issue.message
        and "discount-rate source support" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_reliance_glance_panel_detail():
    text = _otherwise_complete_pdf_text().replace(
        "The report is not a substitute for independent professional advice.",
        "Read the full disclaimer before relying on the report.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_glance_panels"
        and "Reliance at a glance" in issue.message
        and "advice-status limit" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_derived_technical_assumptions_marker():
    text = _otherwise_complete_pdf_text().replace(
        "Derived technical assumptions",
        "Technical assumptions",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_pdf_marker"
        and "Derived technical assumptions" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_derived_technical_assumptions_detail():
    text = (
        _otherwise_complete_pdf_text()
        .replace("Discount rate, terminal growth and forecast horizon", "technical assumptions")
        .replace("forecast horizon, WACC, terminal growth or discount-rate scenarios", "technical inputs")
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_pdf_derived_technical_assumption_detail"
        and "terminal growth" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_intentionally_not_asked_marker():
    text = _otherwise_complete_pdf_text().replace(
        "Questions intentionally not asked",
        "Avoided technical inputs",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_pdf_marker"
        and "Questions intentionally not asked" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_report_letter_marker():
    text = _otherwise_complete_pdf_text().replace(
        "Report letter",
        "Engagement note",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_pdf_marker"
        and "Report letter" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_all_numbered_sections():
    text = _otherwise_complete_pdf_text().replace(
        "15 Multiples Cross-check",
        "15 Market Cross-check",
        1,
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_numbered_section_mismatch"
        and "15 Multiples Cross-check" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_numbered_section_order():
    text = _swap_first_occurrence(
        _otherwise_complete_pdf_text(),
        "14 Indicative Valuation Summary",
        "15 Multiples Cross-check",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_numbered_section_order"
        and "15 Multiples Cross-check" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_scope_exclusion_detail():
    text = _otherwise_complete_pdf_text().replace(
        "buyer-specific synergy assessment",
        "transaction-specific assessment",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_pdf_scope_exclusions"
        and "buyer-specific synergy assessment" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_comparable_caveat():
    text = _otherwise_complete_pdf_text()
    replacements = {
        (
            "Public benchmark evidence is broad sector context, not directly comparable "
            "private-company pricing. It is used as a reasonableness cross-check."
        ): "The evidence directly prices the subject business.",
        "Limitations explained as a reasonableness check": (
            "No limitation noted"
        ),
        "Explains that public evidence is used for context and cross-checking, not as a direct private-company price.": (
            "Summarises the evidence."
        ),
    }
    for old, new in replacements.items():
        assert old in text
        text = text.replace(old, new)

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_pdf_comparable_caveat"
        and "not-directly-comparable limitation" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_rejects_non_public_source_urls():
    text = _otherwise_complete_pdf_text() + "\nInternal source http://127.0.0.1/internal"

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert audit.metadata["non_public_source_url_count"] == 1
    assert "pdf_non_public_source_urls" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_catches_unfinished_follow_up_language():
    text = _otherwise_complete_pdf_text() + (
        "\nPlease provide additional information before this report can be completed."
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "pdf_unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_catches_more_answer_instruction():
    text = _otherwise_complete_pdf_text() + (
        "\nThe owner should provide more answers before this valuation is complete."
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "pdf_unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_catches_management_follow_up_instruction():
    text = _otherwise_complete_pdf_text() + (
        "\nAsk management to provide signed contracts before this valuation is relied on."
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "pdf_unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_catches_follow_up_item_language():
    text = _otherwise_complete_pdf_text() + "\nCustomer concentration analysis remains a follow-up item."

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "pdf_unfinished_followup_language" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_catches_template_placeholder_language():
    text = _otherwise_complete_pdf_text() + "\nComparable evidence to be confirmed."

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "pdf_placeholder_text" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_catches_draft_language():
    text = _otherwise_complete_pdf_text() + "\nThis preliminary draft valuation is not final."

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "pdf_draft_language" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_catches_legacy_owner_dependency_language():
    text = _otherwise_complete_pdf_text() + "\nOwner dependency / transition should be reviewed."

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "pdf_legacy_owner_dependency_language" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_catches_legacy_private_context_language():
    text = _otherwise_complete_pdf_text() + "\nPrivate buyer context: contract renewal timing."

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "pdf_legacy_private_context_language" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_catches_sale_process_risk_language():
    text = _otherwise_complete_pdf_text() + "\nOne-off legal costs are non-recurring transaction expenditure."

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "pdf_sale_process_risk_language" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_requires_professional_cover_brief():
    audit = audit_valuation_pdf_text(
        _otherwise_complete_pdf_text(cover_brief=False),
        page_count=25,
        demo_mode=True,
    )
    codes = {issue.code for issue in audit.issues}

    assert audit.passed is False
    assert "missing_pdf_cover_marker" in codes
    assert "missing_demo_cover_reliance" in codes
    assert "thin_pdf_page_count" not in codes
    assert "pdf_thin_source_trail" not in codes


def test_valuation_pdf_text_audit_requires_cover_report_basis_strip():
    text = _otherwise_complete_pdf_text().replace(
        "REPORT BASIS\n"
        "Uploaded financials Revenue, earnings and balance sheet\n"
        "Five private inputs Only facts management can confirm\n"
        "Public-source trail Research URLs retained for review\n"
        "AccountIQ model DCF, WACC, multiples and sensitivity\n",
        "",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert "missing_pdf_cover_report_basis" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_requires_cover_brief_before_contents():
    text = _otherwise_complete_pdf_text()
    cover, rest = text.split("VALUATION SNAPSHOT", 1)
    misplaced_cover = rest.replace(
        "Contents",
        "Contents\n" + cover,
        1,
    )

    audit = audit_valuation_pdf_text(
        "DEMO DATA - NOT FOR RELIANCE\nVALUATION SNAPSHOT" + misplaced_cover,
        page_count=25,
        demo_mode=True,
    )

    assert audit.passed is False
    assert "missing_pdf_cover_marker" in {issue.code for issue in audit.issues}
    assert "missing_demo_cover_reliance" in {issue.code for issue in audit.issues}


def test_valuation_pdf_text_audit_requires_cover_valuation_snapshot_detail():
    text = _otherwise_complete_pdf_text().replace(
        "Enterprise value $2,831,000 $2,314,000 $1,898,000\n"
        "Less: net debt $65,000 $65,000 $65,000\n"
        "Indicative equity value $2,766,000 $2,249,000 $1,833,000",
        "Summary values shown later in the report",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_pdf_cover_snapshot"
        and "Enterprise value" in issue.message
        and "Net debt" in issue.message
        and "Indicative equity value" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_cover_net_debt_bridge():
    text = _otherwise_complete_pdf_text().replace(
        "Less: net debt $65,000 $65,000 $65,000\n",
        "",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_pdf_cover_snapshot"
        and "Net debt" in issue.message
        and "Enterprise value" not in issue.message
        and "Indicative equity value" not in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_cover_snapshot_values():
    text = _otherwise_complete_pdf_text()
    for value in (
        "$2,831,000",
        "$2,314,000",
        "$1,898,000",
        "$65,000",
        "$2,766,000",
        "$2,249,000",
        "$1,833,000",
    ):
        text = text.replace(value, "Value not shown")
    text = text.replace(
        "PREPARED FOR Example Limited",
        "Unrelated cover values $1 $2 $3 $4 $5 $6 $7 $8 $9 PREPARED FOR Example Limited",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "thin_pdf_cover_snapshot_values"
        and "Found 0 dollar values" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_complete_high_mid_low_cover_snapshot_values():
    text = _otherwise_complete_pdf_text().replace(
        "Less: net debt $65,000 $65,000 $65,000",
        "Less: net debt $65,000 Not shown Not shown",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "thin_pdf_cover_snapshot_values"
        and "Found 7 dollar values" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_values_on_each_cover_snapshot_row():
    text = _otherwise_complete_pdf_text().replace(
        "Enterprise value $2,831,000 $2,314,000 $1,898,000\n"
        "Less: net debt $65,000 $65,000 $65,000",
        "Enterprise value $2,831,000 $2,314,000 $1,898,000 Extra valuation values $65,000 $65,000 $65,000\n"
        "Less: net debt Not shown Not shown Not shown",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_cover_snapshot_rows"
        and "Net debt: 0 dollar values" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_management_input_trail():
    text = _otherwise_complete_pdf_text().replace(
        "Management input - Valuation purpose Management-confirmed private input Frames the report scope, reliance wording and valuation conclusion.\n"
        "Management input - Owner or key-person dependency Management-confirmed private input Informs continuity, handover risk, transition risk and specific-risk commentary.\n"
        "Management input - Largest-customer concentration Management-confirmed private input Informs revenue-retention risk, diligence focus and concentration commentary.\n"
        "Management input - Revenue predictability Management-confirmed private input Informs cash-flow reliability, contract-security commentary and forecast support.\n"
        "Management input - Revenue outlook Management-confirmed private input Informs the short-term growth assumption or the decision to derive growth from uploaded financial history.\n",
        "",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)
    codes = {issue.code for issue in audit.issues}

    assert audit.passed is False
    assert "missing_pdf_management_input_trail" in codes
    assert "thin_pdf_page_count" not in codes
    assert "pdf_thin_source_trail" not in codes


def test_valuation_pdf_text_audit_requires_management_input_rationale():
    text = _otherwise_complete_pdf_text().replace(
        "Informs continuity, handover risk, transition risk and specific-risk commentary.",
        "Used as general owner context.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_management_input_trail_detail"
        and "Owner or key-person dependency" in issue.message
        and "continuity" in issue.message
        and "handover risk" in issue.message
        and "transition risk" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_management_input_basis():
    text = _otherwise_complete_pdf_text().replace(
        "Management input - Owner or key-person dependency Management-confirmed private input Informs continuity, handover risk, transition risk and specific-risk commentary.",
        "Management input - Owner or key-person dependency Informs continuity, handover risk, transition risk and specific-risk commentary.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "incomplete_pdf_management_input_trail_detail"
        and "Owner or key-person dependency" in issue.message
        and "management-confirmed private input basis" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_separated_front_matter_blocks():
    owner_rows = (
        "Management input - Valuation purpose Management-confirmed private input Frames the report scope, reliance wording and valuation conclusion.\n"
        "Management input - Owner or key-person dependency Management-confirmed private input Informs continuity, handover risk, transition risk and specific-risk commentary.\n"
        "Management input - Largest-customer concentration Management-confirmed private input Informs revenue-retention risk, diligence focus and concentration commentary.\n"
        "Management input - Revenue predictability Management-confirmed private input Informs cash-flow reliability, contract-security commentary and forecast support.\n"
        "Management input - Revenue outlook Management-confirmed private input Informs the short-term growth assumption or the decision to derive growth from uploaded financial history.\n"
    )
    text = _otherwise_complete_pdf_text().replace(
        "Management input trail\n" + owner_rows + "Evidence and model basis",
        owner_rows + "Management input trail\nEvidence and model basis",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "pdf_front_matter_structure"
        and "Management input - Valuation purpose" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_visible_source_hierarchy():
    text = _otherwise_complete_pdf_text().replace(
        "AccountIQ valuation calculations",
        "internal calculations",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=True)

    assert audit.passed is False
    assert any(
        issue.code == "missing_pdf_source_hierarchy"
        and "AccountIQ valuation calculations" in issue.message
        for issue in audit.issues
    )


def test_valuation_pdf_text_audit_requires_live_cover_reliance():
    text = _otherwise_complete_pdf_text(demo_mode=False).replace(
        "Indicative valuation support only; obtain independent professional advice before reliance.",
        "Confidential indicative valuation.",
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=False)
    codes = {issue.code for issue in audit.issues}

    assert audit.passed is False
    assert "missing_live_cover_reliance" in codes
    assert "unexpected_demo_label" not in codes


def test_valuation_pdf_text_audit_rejects_demo_language_in_live_report():
    text = (
        _otherwise_complete_pdf_text(demo_mode=False)
        + "\nThe sample company summary should not appear in a live report."
    )

    audit = audit_valuation_pdf_text(text, page_count=25, demo_mode=False)

    assert audit.passed is False
    assert "pdf_demo_language_in_live_report" in {issue.code for issue in audit.issues}
