"""Reusable quality audits for AccountIQ valuation report artifacts.

The strict generation validators decide whether a report can be marked ready.
These audits are intentionally higher level: they give developers and admins a
single checklist-style result for comparing deterministic samples or live smoke
artifacts against the professional valuation-pack target.
"""
from __future__ import annotations

import html as html_lib
import ipaddress
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from report_prompts import SECTION_SCHEMAS, TABLE_SECTIONS_VALUATION


_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_MONEY_VALUE_RE = re.compile(r"\$[\d,]+(?:\.\d+)?")
_SAFE_EXTERNAL_SOURCE_LINK_RE = re.compile(
    r"<a\b(?=[^>]*\bhref=[\"']https?://[^\"']+[\"'])"
    r"(?=[^>]*\btarget=[\"']_blank[\"'])"
    r"(?=[^>]*\brel=[\"'][^\"']*\bnoopener\b[^\"']*\bnoreferrer\b[^\"']*[\"'])"
    r"[^>]*>",
    re.IGNORECASE,
)
_NON_ASCII_DASH_ARTIFACTS = ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212")
_UNICODE_LAYOUT_ARTIFACTS = ("\u2022", *_NON_ASCII_DASH_ARTIFACTS, "(cid:")
_HTML_LAYOUT_ARTIFACTS = ("\u2022", *_NON_ASCII_DASH_ARTIFACTS, "(cid:")
_IMPLEMENTATION_MARKERS = (
    "python-built",
    "python-computed",
    "model-computed",
    "json object",
    "code fence",
    "system prompt",
    "user prompt",
    "openai",
    "language model",
    "ai narrative",
    "computed valuation rows",
    "computed financial-performance table",
    "computed sensitivity matrix",
    "source/evidence tables",
)
_INTERNAL_VALUATION_KEY_MARKERS = (
    "management_custom_override",
    "management_outlook_lower",
    "management_outlook_steady",
    "management_outlook_modest_growth",
    "management_outlook_strong_growth",
    "owner_custom_override",
    "owner_outlook_lower",
    "owner_outlook_steady",
    "owner_outlook_modest_growth",
    "owner_outlook_strong_growth",
    "historical_revenue_cagr_capped",
    "insufficient_history_fallback",
    "extracted_operating_line_items",
    "extracted_current_totals",
    "insufficient_history_zero_assumption",
)
_RAW_VALUATION_INTAKE_KEY_MARKERS = (
    "valuation_purpose",
    "owner_dependency",
    "customer_concentration",
    "revenue_quality",
    "revenue_outlook",
    "private_context",
    "company_website",
    "company_location",
    "public_source_urls",
    "replacement_manager_cost",
    "debt_override",
    "surplus_assets",
    "custom_growth_rate",
    "understand_value",
    "sale_or_transaction",
    "shareholder_or_employee_scheme",
    "succession_planning",
    "finance_or_investment",
    "under_10",
    "10_to_25",
    "over_25",
    "consumer_or_diversified",
    "mostly_contract",
    "mostly_one_off",
    "modest_growth",
    "strong_growth",
    "not_sure",
)
_PLACEHOLDER_MARKERS = (
    "tbd",
    "tbc",
    "to be confirmed",
    "to be advised",
    "lorem ipsum",
    "[insert",
    "[placeholder",
    "placeholder",
    "not generated",
    "generation error",
    "could not be parsed",
    "[section",
    "please retry]",
)
_DRAFT_LANGUAGE_MARKERS = (
    "first draft",
    "rough draft",
    "working draft",
    "preliminary draft",
    "draft report",
    "draft valuation",
    "draft output",
    "this is a draft",
    "not final",
    "not yet final",
    "work in progress",
)
_LEGACY_OWNER_DEPENDENCY_MARKERS = (
    "owner dependency",
    "owner-dependency",
    "owner dependency / transition",
    "management input - owner dependency",
    "buyer reliance on the owner",
    "responsibility is shared across the owner and team",
    "business depends heavily on the owner",
    "owner is important day to day",
)
_LEGACY_PRIVATE_CONTEXT_MARKERS = (
    "private buyer context",
    "buyer-only context",
    "buyer only context",
    "optional buyer context",
)
_LIVE_DEMO_LANGUAGE_MARKERS = (
    "demo indicative valuation",
    "demo figures",
    "demo data",
    "simulated research",
    "simulated valuation",
    "sample public-source research",
    "sample report's",
    "sample report.",
    "the sample company",
    "not for reliance",
)
_SALE_PROCESS_RISK_MARKERS = (
    "buyer diligence focus",
    "buyer confidence",
    "buyer diligence should",
    "buyer may require",
    "may reduce buyer confidence",
    "post-transaction continuity",
    "buyer review",
    "buyer context",
    "before a transaction",
    "transaction expenditure",
)
UNFINISHED_FOLLOWUP_MARKERS = (
    "please provide",
    "please upload",
    "provide additional information",
    "provide more information",
    "provide more documents",
    "provide more answers",
    "provide further information",
    "additional information is required",
    "additional information is needed",
    "we need additional information",
    "requires follow-up information",
    "requires further information",
    "follow-up information is required",
    "follow-up information is needed",
    "follow-up item",
    "follow-up items",
    "request further information",
    "request more information",
    "upload additional documents",
    "upload more documents",
    "send additional documents",
    "send more documents",
    "send us more information",
    "ask your accountant to provide",
    "ask an accountant to provide",
    "ask the owner to provide",
    "ask management to provide",
    "ask the user to provide",
    "management should provide",
    "the user should provide",
    "user should provide",
    "contact us to complete",
    "speak to us to complete",
    "cannot complete the report",
    "cannot complete this report",
    "this report cannot be completed",
    "unable to complete the report",
    "unable to complete this report",
    "once you provide",
)
_PDF_MANAGEMENT_INPUT_TRAIL_MARKERS = (
    "Management input - Valuation purpose",
    "Management input - Owner or key-person dependency",
    "Management input - Largest-customer concentration",
    "Management input - Revenue predictability",
    "Management input - Revenue outlook",
)
_MANAGEMENT_INPUT_MARKER_PREFIX = "Management input - "
_COVER_SNAPSHOT_MARKERS = (
    "Valuation snapshot",
    "Output",
    "High",
    "Mid",
    "Low",
    "Enterprise value",
    "Net debt",
    "Indicative equity value",
)
_COVER_SNAPSHOT_MISSING_VALUE_MARKERS = (
    "not shown",
    "value not shown",
    "values not shown",
)
_COVER_REPORT_BASIS_MARKERS = (
    "Report basis",
    "Uploaded financials",
    "Five private inputs",
    "Public-source trail",
    "AccountIQ model",
)
_CASH_FLOW_SCHEDULE_ROW_LABELS = (
    "Revenue",
    "EBITDA",
    "EBIT",
    "Tax",
    "Maintenance capex",
    "Change in operating working capital",
    "Free cash flow to firm",
    "Discounted free cash flow",
)
_PROFESSIONAL_REPORT_MARKERS = (
    "Contents",
    "Basis of preparation",
    "Report letter",
    "Prepared for",
    "Prepared by",
    "Preparer role",
    "Report channel",
    "Purpose and reliance",
    "Important limitation",
    "Information basis",
    "Scope exclusions",
    "Management input trail",
    "Evidence and model basis",
    "Derived technical assumptions",
    "Questions intentionally not asked",
    "01 Introduction",
    "02 Executive Summary",
    "Valuation conclusion at a glance",
    "Valuation range visual",
    "Business context at a glance",
    "Market context at a glance",
    "Methodology at a glance",
    "Trading performance at a glance",
    "Financial trend visual",
    "Margin and growth at a glance",
    "Normalisation impact at a glance",
    "Normalised EBITDA bridge",
    "How the discount rate drives the range",
    "WACC build visual",
    "Enterprise-to-equity bridge",
    "Enterprise-to-equity visual",
    "Valuation approach selection",
    "How the market cross-check is used",
    "Implied multiple reconciliation",
    "11 Valuation Approach and Assumptions",
    "Assumption basis at a glance",
    "13 Discounted Cash Flow Analysis",
    "DCF value build visual",
    "DCF forecast bridge at a glance",
    "Valuation range at a glance",
    "16 Sensitivity and Specific Risks",
    "Sensitivity spread visual",
    "Sensitivity takeaway at a glance",
    "18 Sources and References",
    "Comparable evidence at a glance",
    "Source trail at a glance",
    "19 Disclaimer",
    "Reliance at a glance",
    "20 General Principles",
    "21 Glossary",
    "Mid-case forecast cash-flow schedule",
    "Specific risk factors",
)
_VALUATION_SECTION_TITLES = {
    "introduction": "Introduction",
    "executive_summary": "Executive Summary",
    "business_overview": "Overview",
    "market_position": "Market Position",
    "about_business_valuations": "About Business Valuations",
    "valuation_methodology": "Valuation Methodology Adopted",
    "financial_performance": "Financial Performance",
    "financial_ratio_analysis": "Historical Ratio Analysis",
    "normalisations_schedule": "Normalisations",
    "balance_sheet_summary": "Balance Sheet Summary",
    "valuation_assumptions": "Valuation Approach and Assumptions",
    "wacc_assumptions": "Weighted Average Cost of Capital",
    "dcf_analysis": "Discounted Cash Flow Analysis",
    "valuation_summary": "Indicative Valuation Summary",
    "multiples_crosscheck": "Multiples Cross-check",
    "sensitivity_and_risks": "Sensitivity and Specific Risks",
    "comparable_evidence": "Comparable Evidence Appendix",
    "sources": "Sources and References",
    "disclaimer": "Disclaimer",
    "general_principles": "General Principles",
    "glossary": "Glossary",
}
_CREDIT_SECTION_TITLES = {
    "executive_summary": "Executive Summary",
    "transaction_summary": "Transaction Summary",
    "sources_and_uses": "Sources & Uses",
    "borrower_and_sponsor_profile": "Borrower & Sponsor Profile",
    "facilities_requested": "Facilities Requested",
    "security_package": "Security Package",
    "financial_performance_forecast": "Financial Performance & Forecast",
    "coverage_and_sensitivity": "Coverage Ratios & Sensitivity",
    "balance_sheet_debt_capacity": "Balance Sheet & Debt Capacity",
    "industry_and_competitive_landscape": "Industry & Competitive Landscape",
    "proposed_covenants": "Proposed Covenants",
    "key_risks_and_mitigants": "Key Risks & Mitigants",
    "conditions_precedent": "Conditions Precedent",
    "recommendation": "Recommendation",
    "disclaimer": "Disclaimer",
}
_CREDIT_REQUIRED_COVER_MARKERS = (
    "Prepared for",
    "Prepared by",
    "Report type",
    "Reference",
    "Prepared date",
    "Purpose",
    "Credit posture",
    "Reliance",
)
_CREDIT_REQUIRED_BASIS_MARKERS = (
    "Report basis",
    "Uploaded financials",
    "Lender inputs",
    "Public client context",
    "Debt-capacity model",
)
_CREDIT_REQUIRED_BODY_MARKERS = (
    "screening-only",
    "requested facility",
    "DSCR",
    "ICR",
    "LVR",
    "NTOA",
    "supportable debt",
    "conditions precedent",
    "proposed lender controls",
)
_CREDIT_VALUATION_ONLY_MARKERS = (
    "valuation snapshot",
    "valuation date",
    "basis of value",
    "indicative fair-market value",
    "indicative valuation pack",
    "reliance is limited to the valuation purpose stated",
    "valuation conclusion at a glance",
    "wacc build visual",
    "dcf value build visual",
)
_CREDIT_PLACEHOLDER_MARKERS = tuple(
    marker for marker in _PLACEHOLDER_MARKERS if marker not in {"tbc", "to be confirmed"}
)
_SCOPE_EXCLUSION_CONCEPTS = {
    "audit or assurance engagement": (("audit",), ("assurance",)),
    "legal or tax advice": (("legal",), ("tax",)),
    "fairness opinion": (("fairness opinion",),),
    "buyer-specific synergy assessment": (
        (
            "buyer-specific synergy",
            "buyer specific synergy",
            "buyer-specific synergies",
            "buyer specific synergies",
        ),
    ),
}
_TECHNICAL_ASSUMPTION_EXCLUSION_CONCEPTS = {
    "discount rate or WACC": (("discount rate", "wacc"),),
    "terminal growth": (("terminal growth",),),
    "forecast horizon or period": (("forecast horizon", "forecast period"),),
}
_NOT_SURE_REVENUE_OUTLOOK_MARKERS = (
    "management input - revenue outlook not sure - growth derived from uploaded financial history",
    "management input revenue outlook not sure - growth derived from uploaded financial history",
    "management input - revenue outlook no specific forecast provided; growth derived from uploaded financial history",
    "management input revenue outlook no specific forecast provided; growth derived from uploaded financial history",
    "revenue outlook no specific forecast provided; growth derived from uploaded financial history",
)
_MODEST_GROWTH_OUTLOOK_MARKERS = (
    "management outlook: modest growth",
    "revenue outlook modest growth",
    "revenue outlook and pipeline modest growth",
    "modest growth supports the base forecast",
)
_SOURCE_HIERARCHY_CONCEPTS = {
    "uploaded financial information": (
        (
            "uploaded financial statements",
            "uploaded financial information",
            "uploaded financial data",
            "uploaded financials",
        ),
    ),
    "management-confirmed private inputs": (
        (
            "management-confirmed private inputs",
            "management confirmed private inputs",
            "management-confirmed private input",
            "management confirmed private input",
        ),
    ),
    "public research": (
        (
            "public research",
            "public-source research",
            "public source research",
        ),
    ),
    "AccountIQ valuation calculations": (("accountiq valuation calculations",),),
}
_COMPARABLE_CAVEAT_ROLE_MARKERS = (
    "reasonableness check",
    "reasonableness cross-check",
    "cross-check",
    "cross check",
)
_COMPARABLE_CAVEAT_LIMITATION_MARKERS = (
    "not directly comparable",
    "not a direct price",
    "not a direct pricing",
    "not a direct private-company",
    "not a perfect private-company match",
    "broad-sector",
    "broad sector",
    "broad listed-company",
    "broad listed company",
    "larger and more liquid",
    "more liquid",
    "differs in scale",
    "differ in scale",
    "scale, growth",
    "customer mix",
    "contract security",
)
_MANAGEMENT_INPUT_TRAIL_DETAIL_CONCEPTS = (
    (
        "Valuation purpose",
        (
            ("report scope", ("report scope",)),
            ("reliance", ("reliance",)),
            ("valuation conclusion", ("valuation conclusion",)),
        ),
    ),
    (
        "Owner or key-person dependency",
        (
            ("continuity", ("continuity",)),
            ("handover risk", ("handover",)),
            ("transition risk", ("transition risk",)),
            ("specific-risk commentary", ("specific-risk", "specific risk")),
        ),
    ),
    (
        "Largest-customer concentration",
        (
            ("revenue-retention risk", ("revenue-retention", "revenue retention")),
            ("diligence focus", ("diligence",)),
            ("concentration commentary", ("concentration",)),
        ),
    ),
    (
        "Revenue predictability",
        (
            ("cash-flow reliability", ("cash-flow", "cash flow")),
            ("contract-security commentary", ("contract-security", "contract security")),
            ("forecast support", ("forecast support",)),
        ),
    ),
    (
        "Revenue outlook",
        (
            ("short-term growth assumption", ("short-term growth", "growth assumption")),
            ("derived from uploaded financial history", ("derive growth", "uploaded financial history")),
        ),
    ),
)
_INTERPRETATION_PANEL_CONCEPTS = (
    (
        "How the discount rate drives the range",
        ("WACC build visual", "13 Discounted Cash Flow Analysis"),
        (
            (
                "lower WACC upper-valuation link",
                (
                    ("lower wacc", "upper valuation"),
                    ("discounted less", "upper valuation"),
                    ("high valuation discount rate", "upper valuation"),
                ),
            ),
            (
                "base discount-rate central case",
                (
                    ("base discount-rate", "central valuation"),
                    ("base discount rate", "central valuation"),
                    ("mid valuation discount rate", "central"),
                ),
            ),
            (
                "higher WACC lower-valuation link",
                (
                    ("higher wacc", "lower valuation"),
                    ("higher wacc", "more risk"),
                    ("low valuation discount rate", "higher wacc"),
                ),
            ),
            (
                "illiquidity discount visibility",
                (
                    ("illiquidity discount", "explicit"),
                    ("marketability discount", "explicit"),
                ),
            ),
        ),
    ),
    (
        "How the market cross-check is used",
        ("Implied multiple reconciliation", "16 Sensitivity and Specific Risks"),
        (
            (
                "researched EV/EBITDA evidence",
                (
                    ("ev/ebitda", "comparable evidence"),
                    ("market multiple range", "researched comparable evidence"),
                ),
            ),
            (
                "maintainable EBITDA basis",
                (
                    ("maintainable ebitda", "earnings base"),
                    ("maintainable earnings", "market cross-check"),
                ),
            ),
            (
                "reasonableness not primary conclusion",
                (
                    ("reasonableness", "not replace"),
                    ("reasonableness", "primary dcf"),
                    ("cross-check", "not replace"),
                ),
            ),
            (
                "enterprise-to-equity bridge context",
                (
                    ("enterprise-to-equity bridge",),
                    ("enterprise to equity bridge",),
                ),
            ),
        ),
    ),
)
_AT_A_GLANCE_PANEL_CONCEPTS = (
    (
        "Business context at a glance",
        ("04 Market Position", "Market context at a glance", "Methodology at a glance"),
        (
            (
                "owner/key-person context",
                (
                    (
                        "owner or key-person dependency",
                        "management-supplied context",
                        "transition",
                        "key-person risk",
                    ),
                    ("owner or key-person dependency", "responsibility is shared", "key-person risk"),
                    ("owner or key-person dependency", "handover risk", "transition risk"),
                ),
            ),
            (
                "customer-concentration context",
                (
                    ("customer concentration", "10% to 25%", "large customers"),
                    ("customer concentration", "revenue is exposed", "large customers"),
                    ("customer concentration", "revenue-retention risk"),
                ),
            ),
            (
                "revenue-predictability context",
                (
                    ("revenue predictability", "recurring", "one-off revenue"),
                    ("revenue predictability", "recurring", "project-based revenue"),
                    ("revenue predictability", "cash-flow reliability"),
                ),
            ),
            (
                "revenue-outlook context",
                (
                    ("revenue outlook", "no specific forecast provided", "uploaded financial history"),
                    ("revenue outlook", "short-term growth assumption"),
                    ("revenue outlook", "derive growth", "uploaded financial history"),
                ),
            ),
        ),
    ),
    (
        "Valuation conclusion at a glance",
        ("Valuation range visual", "03 Overview", "Business context at a glance"),
        (
            (
                "enterprise-value range",
                (
                    ("enterprise value range", "$", "dcf valuation range"),
                    ("enterprise value range", "$", "primary dcf"),
                    ("enterprise value range", "$", "valuation range"),
                ),
            ),
            (
                "midpoint enterprise value",
                (
                    ("midpoint enterprise value", "$", "central indication"),
                    ("midpoint enterprise value", "$", "net debt"),
                    ("midpoint enterprise value", "$", "enterprise-to-equity"),
                ),
            ),
            (
                "midpoint equity value",
                (
                    ("midpoint equity value", "$", "shareholder"),
                    ("midpoint equity value", "$", "equity bridge"),
                    ("midpoint equity value", "$", "enterprise-to-equity"),
                ),
            ),
            (
                "net-debt adjustment",
                (
                    ("net debt adjustment", "$", "bridge"),
                    ("net-debt adjustment", "$", "bridge"),
                    ("net debt", "$", "valuation scenarios"),
                ),
            ),
        ),
    ),
    (
        "Market context at a glance",
        ("05 About Business Valuations", "Methodology at a glance", "06 Valuation Methodology Adopted"),
        (
            (
                "public-source count context",
                (
                    ("public sources retained", "source urls", "market, profile and benchmark context"),
                    ("public sources retained", "source links", "market"),
                    ("public sources retained", "public evidence trail"),
                ),
            ),
            (
                "benchmark-evidence context",
                (
                    ("benchmark evidence", "public evidence supports", "ev/ebitda context"),
                    ("benchmark evidence", "public evidence supports", "sector"),
                    ("benchmark evidence", "public evidence supports", "market"),
                    ("benchmark evidence", "public-source research", "reasonableness"),
                ),
            ),
            (
                "public-profile support context",
                (
                    (
                        "public profile support",
                        "public sources support",
                        "company-profile",
                        "operating-context",
                    ),
                    ("public profile support", "public sources support", "company profile"),
                    ("public profile support", "operating-context statements"),
                ),
            ),
            (
                "comparability caveat",
                (
                    ("comparability caveat", "limitations explain", "contextual", "direct pricing"),
                    ("comparability caveat", "public evidence", "context and cross-checking", "not a direct price"),
                    ("comparability caveat", "public evidence", "not directly comparable"),
                    ("comparability caveat", "reasonableness cross-check"),
                ),
            ),
        ),
    ),
    (
        "Methodology at a glance",
        ("Valuation approach selection", "07 Financial Performance", "Trading performance at a glance"),
        (
            (
                "primary DCF method",
                (
                    ("primary valuation method", "discounted cash flow", "forecast free cash flows"),
                    ("primary valuation method", "discounted cash flow", "primary valuation basis"),
                    ("discounted cash flow", "forecast free cash flows", "primary valuation basis"),
                ),
            ),
            (
                "discount-rate scenario range",
                (
                    ("discount-rate range", "%", "wacc scenarios", "valuation range"),
                    ("discount-rate range", "%", "high", "midpoint", "low", "wacc"),
                    ("discount rate range", "%", "wacc scenarios", "valuation range"),
                ),
            ),
            (
                "market cross-check role",
                (
                    ("market cross-check", "ev/ebitda", "reasonableness check"),
                    ("market cross-check", "market multiples", "reasonableness check"),
                    ("market cross-check", "researched market multiples"),
                ),
            ),
            (
                "equity bridge role",
                (
                    ("equity bridge", "$", "shareholder value", "debt", "cash", "surplus assets"),
                    ("equity bridge", "$", "enterprise value", "shareholder value"),
                    ("enterprise value", "shareholder value", "debt", "cash", "surplus assets"),
                ),
            ),
        ),
    ),
    (
        "Trading performance at a glance",
        (
            "Financial trend visual",
            "Financial Performance detailed schedule",
            "08 Historical Ratio Analysis",
            "Margin and growth at a glance",
        ),
        (
            (
                "revenue bridge",
                (
                    ("revenue bridge", "$", "historical and forecast period"),
                    ("revenue bridge", "$", "top-line progression"),
                    ("revenue bridge", "$", "forecast period"),
                ),
            ),
            (
                "direct-cost bridge to gross profit",
                (
                    ("direct-cost bridge", "$", "revenue", "gross profit"),
                    ("direct cost bridge", "$", "revenue", "gross profit"),
                    ("direct costs", "$", "cost of sales", "gross profit"),
                ),
            ),
            (
                "gross profit bridge before overheads",
                (
                    ("gross profit bridge", "$", "overheads", "operating expenses"),
                    ("gross profit bridge", "$", "trading margin"),
                    ("gross profit", "$", "before overheads"),
                ),
            ),
            (
                "operating expense bridge to EBITDA",
                (
                    ("operating expense bridge", "$", "gross profit", "ebitda"),
                    ("operating expenses", "$", "gross profit", "ebitda"),
                    ("overhead deduction", "$", "reconcile gross profit to ebitda"),
                ),
            ),
            (
                "EBITDA bridge before normalisation",
                (
                    ("ebitda bridge", "$", "normalisation schedule"),
                    ("ebitda bridge", "$", "operating earnings progression"),
                    ("ebitda bridge", "$", "before the normalisation"),
                ),
            ),
            (
                "EBITDA margin bridge",
                (
                    ("ebitda margin bridge", "16.8%", "19.2%", "operating leverage"),
                    ("ebitda margin bridge", "%", "improving", "stable", "weakening"),
                    ("ebitda margin bridge", "%", "across the period"),
                ),
            ),
            (
                "latest actual EBITDA reference point",
                (
                    ("latest actual ebitda", "$", "before forecast", "valuation adjustments"),
                    ("latest actual ebitda", "$", "earnings reference point"),
                    ("latest actual ebitda", "$", "forecast and valuation adjustments"),
                ),
            ),
        ),
    ),
    (
        "Margin and growth at a glance",
        (
            "Historical Ratio Analysis detailed schedule",
            "Ratio",
            "09 Normalisations",
            "Normalisation impact at a glance",
        ),
        (
            (
                "latest revenue growth",
                (
                    ("latest revenue growth", "8.0%", "uploaded-financials trend table"),
                    ("latest revenue growth", "%", "growth rate"),
                    ("latest revenue growth", "%", "uploaded financials"),
                ),
            ),
            (
                "gross margin bridge",
                (
                    ("gross margin bridge", "60.0%", "63.0%", "direct-cost efficiency"),
                    ("gross margin bridge", "%", "improving", "stable", "weakening"),
                    ("gross margin bridge", "%", "direct cost efficiency"),
                ),
            ),
            (
                "EBITDA margin trend",
                (
                    ("ebitda margin bridge", "16.8%", "19.2%", "operating leverage"),
                    ("ebitda margin bridge", "%", "before valuation adjustments"),
                    ("ebitda margin bridge", "%", "operating leverage"),
                ),
            ),
            (
                "net profit margin trend",
                (
                    ("net profit margin bridge", "10.7%", "12.1%", "after-tax profit conversion"),
                    ("net profit margin bridge", "%", "uploaded financials"),
                    ("net profit margin bridge", "%", "profit conversion trend"),
                ),
            ),
        ),
    ),
    (
        "Normalisation impact at a glance",
        (
            "Normalised EBITDA bridge",
            "Normalisations detailed schedule",
            "10 Balance Sheet Summary",
            "Enterprise-to-equity bridge",
        ),
        (
            (
                "confirmed adjustment count",
                (
                    ("confirmed adjustments", "2", "management-reviewed normalisation items"),
                    ("confirmed adjustments", "2", "maintainable earnings bridge"),
                    ("confirmed adjustments", "management-reviewed", "maintainable earnings"),
                ),
            ),
            (
                "net EBITDA adjustment",
                (
                    ("net ebitda adjustment", "$", "valuation earnings base"),
                    ("net ebitda adjustment", "$", "add-back or deduction"),
                    ("net ebitda adjustment", "$", "before the valuation"),
                ),
            ),
            (
                "largest adjustment review item",
                (
                    ("largest adjustment", "owner remuneration", "$", "management review"),
                    ("largest adjustment", "owner remuneration", "$", "adviser"),
                    ("largest adjustment", "$", "individual normalisation item"),
                ),
            ),
            (
                "normalised EBITDA valuation basis",
                (
                    ("normalised ebitda", "$", "maintainable earnings base", "valuation analysis"),
                    ("normalised ebitda", "$", "maintainable earnings base"),
                    ("normalised ebitda", "$", "valuation analysis"),
                ),
            ),
        ),
    ),
    (
        "Assumption basis at a glance",
        (
            "Valuation Approach and Assumptions detailed schedule",
            "Assumption / input",
            "12 Weighted Average Cost of Capital",
            "13 Discounted Cash Flow Analysis",
            "DCF value build visual",
            "DCF forecast bridge at a glance",
            "WACC build visual",
        ),
        (
            (
                "maintainable earnings source",
                (
                    ("maintainable earnings base", "$", "normalised ebitda"),
                    ("maintainable earnings base", "$", "valuation earnings base"),
                    ("normalised ebitda", "$", "valuation earnings base"),
                ),
            ),
            (
                "growth assumption source",
                (
                    ("growth assumption", "%", "source"),
                    ("growth assumption", "%", "forecast growth assumption"),
                    ("growth assumption", "%", "uploaded revenue history"),
                ),
            ),
            (
                "public research source mix",
                (
                    ("public research inputs", "public market", "inflation", "discount-rate evidence"),
                    ("public research inputs", "public market", "discount-rate evidence"),
                    ("public research inputs", "inflation", "discount-rate evidence"),
                ),
            ),
            (
                "management-confirmed source mix",
                (
                    ("management-confirmed inputs", "management-supplied private inputs", "business-specific assumptions"),
                    ("management-confirmed inputs", "private inputs", "business-specific assumptions"),
                    ("management-confirmed inputs", "5", "management-supplied"),
                ),
            ),
            (
                "technical model source mix",
                (
                    ("technical model inputs", "valuation-model conventions", "assumption basis"),
                    ("technical model inputs", "valuation model conventions", "assumption basis"),
                    ("technical model inputs", "model", "disclosed"),
                ),
            ),
        ),
    ),
    (
        "DCF forecast bridge at a glance",
        (
            "DCF value build visual",
            "Discounted Cash Flow Analysis detailed schedule",
            "14 Indicative Valuation Summary",
            "Valuation range at a glance",
        ),
        (
            (
                "adjusted enterprise-value range",
                (
                    ("adjusted enterprise value range", "$", "illiquidity adjustment"),
                    ("adjusted enterprise value range", "$", "dcf valuation range"),
                    ("adjusted enterprise value range", "$", "private-company illiquidity"),
                ),
            ),
            (
                "midpoint adjusted enterprise value",
                (
                    ("midpoint adjusted enterprise value", "$", "enterprise-to-equity bridge"),
                    ("midpoint adjusted enterprise value", "$", "central dcf indication"),
                    ("midpoint adjusted enterprise value", "$", "central indication"),
                ),
            ),
            (
                "revenue forecast bridge",
                (
                    ("revenue forecast bridge", "$", "mid-case revenue progression"),
                    ("revenue forecast bridge", "$", "explicit five-year forecast period"),
                    ("revenue forecast bridge", "$", "forecast period"),
                ),
            ),
            (
                "free-cash-flow bridge",
                (
                    ("free cash flow bridge", "$", "tax", "capex", "working-capital reinvestment"),
                    ("free cash flow bridge", "$", "free cash flow to firm"),
                    ("free cash flow bridge", "$", "working capital reinvestment"),
                ),
            ),
        ),
    ),
    (
        "Valuation range at a glance",
        (
            "Indicative Valuation Summary detailed schedule",
            "Method / scenario",
            "15 Multiples Cross-check",
            "How the market cross-check is used",
            "16 Sensitivity and Specific Risks",
        ),
        (
            (
                "primary DCF range",
                (
                    ("primary dcf range", "$", "private-company illiquidity adjustment"),
                    ("primary dcf range", "$", "primary enterprise-value range"),
                    ("primary dcf range", "$", "enterprise-value range"),
                ),
            ),
            (
                "midpoint equity value",
                (
                    ("midpoint equity value", "$", "net-debt bridge"),
                    ("midpoint equity value", "$", "shareholder-value indication"),
                    ("midpoint equity value", "$", "central shareholder-value"),
                ),
            ),
            (
                "market cross-check range",
                (
                    ("market cross-check range", "$", "reasonableness check", "not the selected conclusion"),
                    ("market cross-check range", "$", "market multiples", "reasonableness check"),
                    ("market cross-check range", "$", "independent reasonableness check"),
                ),
            ),
            (
                "DCF-versus-multiple midpoint gap",
                (
                    ("dcf vs multiple midpoint", "$", "primary dcf midpoint", "market cross-check midpoint"),
                    ("dcf versus multiple midpoint", "$", "market cross-check midpoint"),
                    ("dcf vs multiple midpoint", "$", "relative to the market cross-check midpoint"),
                ),
            ),
        ),
    ),
    (
        "Sensitivity takeaway at a glance",
        (
            "Sensitivity spread visual",
            "Sensitivity and Specific Risks detailed schedule",
            "17 Comparable Evidence Appendix",
            "Comparable evidence at a glance",
        ),
        (
            (
                "base sensitivity case",
                (
                    ("base sensitivity case", "$", "base growth assumption", "mid wacc"),
                    ("base sensitivity case", "$", "midpoint case"),
                    ("base sensitivity case", "$", "wacc scenario"),
                ),
            ),
            (
                "quantified EV span",
                (
                    ("quantified ev span", "$", "wacc and growth matrix"),
                    ("quantified ev span", "$", "enterprise-value span"),
                    ("quantified ev span", "$", "adjusted enterprise-value span"),
                ),
            ),
            (
                "growth cases without extra questions",
                (
                    ("growth cases tested", "%", "without asking management"),
                    ("growth cases tested", "%", "extra valuation inputs"),
                    ("growth sensitivity range", "without asking management", "extra valuation inputs"),
                ),
            ),
            (
                "short-intake risk coverage",
                (
                    ("specific risk factors", "5", "short management intake"),
                    ("specific risk factors", "qualitative risk factors", "short management intake"),
                    ("specific risk factors", "short management"),
                    ("specific risks covered", "5", "short management intake"),
                ),
            ),
        ),
    ),
    (
        "Comparable evidence at a glance",
        (
            "Comparable Evidence Appendix detailed schedule",
            "18 Sources and References",
            "Source trail at a glance",
            "19 Disclaimer",
        ),
        (
            (
                "public evidence row count",
                (
                    ("evidence rows", "3", "public benchmark and context"),
                    ("evidence rows", "3", "comparable evidence appendix"),
                    ("evidence rows", "public benchmark"),
                ),
            ),
            (
                "source URL trail",
                (
                    ("source urls retained", "3", "source trail"),
                    ("source urls retained", "url", "reader can check"),
                    ("source urls retained", "every evidence row"),
                ),
            ),
            (
                "market multiple support",
                (
                    ("market multiple support", "market evidence supports", "ev/ebitda cross-check"),
                    ("market multiple support", "researched evidence", "ev/ebitda cross-check range"),
                    ("market multiple support", "ev/ebitda", "cross-check range"),
                    ("market multiple support", "researched evidence", "market"),
                ),
            ),
            (
                "comparability caveat",
                (
                    ("comparability caveat", "limitations explained", "reasonableness check"),
                    ("comparability caveat", "public evidence", "context", "direct private-company price"),
                    ("comparability caveat", "reasonableness check", "not a perfect private-company match"),
                    ("comparability caveat", "reasonableness check", "private-company match"),
                    ("comparability caveat", "not a perfect", "private-company match"),
                ),
            ),
        ),
    ),
    (
        "Source trail at a glance",
        (
            "Sources and References detailed schedule",
            "19 Disclaimer",
            "Reliance at a glance",
            "20 General Principles",
        ),
        (
            (
                "public URL evidence trail",
                (
                    ("public urls retained", "public evidence trail"),
                    ("public urls retained", "source links are retained"),
                    ("source links", "public evidence trail"),
                ),
            ),
            (
                "discount-rate source support",
                (
                    ("discount-rate support", "public sources retained", "wacc inputs"),
                    ("discount-rate support", "public sources support", "wacc"),
                    ("discount-rate support", "public sources support", "risk-free"),
                    ("discount-rate support", "public sources support", "equity-risk-premium"),
                    ("discount-rate support", "public sources support", "beta"),
                ),
            ),
            (
                "terminal-growth source support",
                (
                    ("terminal-growth support", "inflation source retained", "terminal growth"),
                    ("terminal-growth support", "public sources support", "inflation"),
                    ("terminal-growth support", "public sources support", "long-term growth"),
                    ("terminal growth support", "public sources support", "inflation"),
                    ("terminal growth support", "public sources support", "long-term growth"),
                ),
            ),
            (
                "business-context source support",
                (
                    ("business context support", "public profile sources retained", "business context"),
                    ("business context support", "public sources support", "company-profile"),
                    ("business context support", "public sources support", "market-context"),
                    ("business context support", "public sources support", "company profile"),
                    ("business context support", "public sources support", "market context"),
                ),
            ),
        ),
    ),
    (
        "Reliance at a glance",
        ("Indicative purpose and reliance", "20 General Principles", "21 Glossary"),
        (
            (
                "intended-use limit",
                (
                    ("intended use", "stated purpose"),
                    ("intended use", "valuation purpose"),
                    ("reliance is limited", "purpose"),
                ),
            ),
            (
                "advice-status limit",
                (
                    ("advice status", "independent professional advice"),
                    ("not a substitute", "independent professional advice"),
                ),
            ),
            (
                "information-reliance basis",
                (
                    ("information reliance", "management"),
                    ("information reliance", "public inputs"),
                    ("management-supplied", "extracted financials", "identified sources"),
                ),
            ),
            (
                "verification-status limit",
                (
                    ("verification status", "not audited"),
                    ("verification status", "not assurance"),
                    ("not an audit", "assurance"),
                ),
            ),
            (
                "third-party reliance limit",
                (
                    ("third-party reliance", "restricted"),
                    ("third-party reliance", "no responsibility"),
                    ("third parties", "should not rely"),
                ),
            ),
        ),
    ),
)
_VISUAL_PANEL_CONCEPTS = (
    (
        "Valuation range visual",
        (
            "Executive Summary detailed schedule",
            "Indicative valuation High Mid Low",
            "03 Overview",
            "Business context at a glance",
        ),
        (
            (
                "low-mid-high visual premise",
                (
                    ("low", "midpoint", "high", "valuation schedules"),
                    ("low", "midpoint", "high", "cases"),
                ),
            ),
            (
                "enterprise-value visual row",
                (
                    ("enterprise value", "operating-business value", "net-debt bridge", "$"),
                    ("enterprise value", "operating-business value", "net debt bridge", "$"),
                    ("enterprise value", "net-debt bridge", "$"),
                    ("enterprise value", "net debt bridge", "$"),
                ),
            ),
            (
                "enterprise-value midpoint marker",
                (
                    ("enterprise value", "mid", "$"),
                    ("enterprise value", "midpoint", "$"),
                ),
            ),
            (
                "indicative-equity visual row",
                (
                    ("indicative equity value", "shareholder-value range", "$"),
                    ("indicative equity value", "shareholder value range", "$"),
                    ("indicative equity value", "debt", "cash", "surplus assets", "$"),
                ),
            ),
            (
                "indicative-equity midpoint marker",
                (
                    ("indicative equity value", "mid", "$"),
                    ("indicative equity value", "midpoint", "$"),
                ),
            ),
        ),
    ),
    (
        "DCF value build visual",
        (
            "Discounted Cash Flow Analysis detailed schedule",
            "DCF item High valuation",
            "DCF forecast bridge at a glance",
            "14 Indicative Valuation Summary",
        ),
        (
            (
                "mid-case value-build premise",
                (
                    ("mid-case", "discounted cash flows", "terminal value", "adjusted enterprise value"),
                    ("mid case", "discounted cash flows", "terminal value", "adjusted enterprise value"),
                ),
            ),
            (
                "explicit forecast cash-flow PV",
                (
                    ("pv explicit fcff", "$", "five-year forecast cash flows"),
                    ("pv explicit fcff", "$", "forecast cash flows"),
                    ("pv explicit fcff", "$", "present value", "cash flows"),
                    ("explicit fcff", "$", "forecast cash flows"),
                ),
            ),
            (
                "terminal-value PV",
                (
                    ("pv terminal value", "$", "continuing value"),
                    ("pv terminal value", "$", "explicit forecast period"),
                    ("terminal value", "$", "continuing value"),
                ),
            ),
            (
                "enterprise-value-before-illiquidity",
                (
                    ("ev before illiquidity", "$", "private-company discount"),
                    ("enterprise value before illiquidity", "$", "private-company discount"),
                    ("ev before illiquidity", "$", "marketability adjustment"),
                ),
            ),
            (
                "illiquidity-discount bridge",
                (
                    ("illiquidity discount", "$", "marketability adjustment"),
                    ("illiquidity discount", "$", "private-company marketability"),
                ),
            ),
            (
                "adjusted-enterprise-value result",
                (
                    ("adjusted enterprise value", "$", "valuation summary"),
                    ("adjusted enterprise value", "$", "operating-business value"),
                    ("adjusted enterprise value", "$", "operating business value"),
                ),
            ),
        ),
    ),
    (
        "WACC build visual",
        (
            "Weighted Average Cost of Capital detailed schedule",
            "Component High valuation",
            "13 Discounted Cash Flow Analysis",
            "DCF forecast bridge at a glance",
        ),
        (
            (
                "mid-case discount-rate build premise",
                (
                    ("mid-case", "discount-rate build", "public market inputs", "illiquidity discount"),
                    ("mid case", "discount-rate build", "public market inputs", "illiquidity discount"),
                    ("mid-case", "discount rate build", "public market inputs", "illiquidity discount"),
                    ("mid case", "discount rate build", "public market inputs", "illiquidity discount"),
                ),
            ),
            (
                "risk-free-rate input",
                (
                    ("risk-free rate", "%", "public market base return"),
                    ("risk-free rate", "%", "company and sector risk"),
                ),
            ),
            (
                "beta-adjusted premium input",
                (
                    ("beta-adjusted risk premium", "%", "total beta", "equity risk premium"),
                    ("beta adjusted risk premium", "%", "total beta", "equity risk premium"),
                ),
            ),
            (
                "mid-WACC result",
                (
                    ("mid wacc", "%", "mid-case forecast cash flows"),
                    ("mid wacc", "%", "mid case forecast cash flows"),
                    ("wacc", "%", "discount rate applied"),
                ),
            ),
            (
                "illiquidity discount visibility",
                (
                    ("illiquidity discount", "%", "private-company marketability"),
                    ("illiquidity discount", "%", "after dcf value"),
                ),
            ),
            (
                "public source inputs",
                (
                    ("source inputs", "erp", "beta", "valuation evidence trail"),
                    ("public research inputs", "erp", "beta"),
                ),
            ),
            (
                "derived technical inputs",
                (
                    ("technical inputs", "derived", "valuation-model inputs"),
                    ("wacc", "beta", "equity-risk-premium", "derived", "valuation-model inputs"),
                ),
            ),
        ),
    ),
    (
        "Enterprise-to-equity visual",
        (
            "Balance Sheet Summary detailed schedule",
            "Balance sheet item Value",
            "11 Valuation Approach and Assumptions",
            "Assumption basis at a glance",
        ),
        (
            (
                "enterprise-to-equity premise",
                (
                    ("operating-business value", "shareholder value", "balance-sheet inputs"),
                    ("operating business value", "shareholder value", "balance-sheet inputs"),
                    ("operating-business value", "shareholder value", "balance sheet inputs"),
                    ("operating business value", "shareholder value", "balance sheet inputs"),
                ),
            ),
            (
                "midpoint enterprise value bridge start",
                (
                    ("midpoint enterprise value", "$", "before debt", "cash", "surplus"),
                    ("midpoint enterprise value", "$", "operating-business value"),
                    ("midpoint enterprise value", "$", "operating business value"),
                ),
            ),
            (
                "net-debt bridge adjustment",
                (
                    ("less net debt", "$", "interest-bearing debt", "available cash"),
                    ("less net debt", "$", "interest bearing debt", "available cash"),
                    ("net debt", "$", "interest-bearing debt", "cash"),
                ),
            ),
            (
                "surplus-assets bridge adjustment",
                (
                    ("surplus assets", "$", "non-operating assets"),
                    ("surplus assets", "$", "non operating assets"),
                    ("surplus assets", "$", "added back"),
                ),
            ),
            (
                "midpoint equity value bridge result",
                (
                    ("midpoint equity value", "$", "shareholder value", "balance-sheet bridge"),
                    ("midpoint equity value", "$", "shareholder value", "balance sheet bridge"),
                    ("midpoint equity value", "$", "indicative shareholder value"),
                ),
            ),
        ),
    ),
    (
        "Normalised EBITDA bridge",
        (
            "Normalisations detailed schedule",
            "Adjustment Amount Rationale",
            "10 Balance Sheet Summary",
            "Enterprise-to-equity bridge",
        ),
        (
            (
                "maintainable-earnings bridge premise",
                (
                    ("uploaded operating earnings", "maintainable ebitda", "valuation"),
                    ("uploaded operating earnings", "maintainable earnings", "valuation"),
                ),
            ),
            (
                "uploaded-EBITDA starting point",
                (
                    ("uploaded ebitda basis", "$", "uploaded financial statements"),
                    ("uploaded ebitda basis", "$", "starting earnings base"),
                ),
            ),
            (
                "net-normalisation adjustment",
                (
                    ("net normalisation", "$", "management-reviewed"),
                    ("net normalisation", "$", "add-backs"),
                    ("net normalisation", "$", "deductions"),
                ),
            ),
            (
                "normalised-EBITDA result",
                (
                    ("normalised ebitda", "$", "maintainable earnings base"),
                    ("normalised ebitda", "$", "dcf", "market-multiple"),
                    ("normalised ebitda", "$", "dcf", "market multiple"),
                ),
            ),
            (
                "earnings-review source",
                (
                    ("owner review", "earnings-adjustment review", "uploaded accounts"),
                    ("owner review", "earnings adjustment review", "uploaded accounts"),
                    ("earnings bridge", "earnings-adjustment review", "uploaded accounts"),
                ),
            ),
            (
                "accounts-and-review source basis",
                (
                    ("source basis", "accounts", "review"),
                    ("uploaded accounts", "confirmed adjustment rows"),
                ),
            ),
            (
                "valuation-use consistency",
                (
                    ("valuation use", "dcf", "multiples"),
                    ("same normalised ebitda", "valuation methods"),
                ),
            ),
        ),
    ),
    (
        "Sensitivity spread visual",
        (
            "Sensitivity takeaway at a glance",
            "Sensitivity and Specific Risks detailed schedule",
            "Growth assumption High valuation",
            "17 Comparable Evidence Appendix",
            "Comparable evidence at a glance",
        ),
        (
            (
                "downside-base-upside premise",
                (
                    ("downside", "base", "upside", "adjusted enterprise value"),
                    ("downside", "base", "upside", "sensitivity analysis"),
                ),
            ),
            (
                "adjusted-enterprise-value sensitivity row",
                (
                    ("adjusted enterprise value sensitivity", "$"),
                    ("adjusted enterprise value", "sensitivity", "$"),
                ),
            ),
            (
                "growth-and-WACC case range",
                (
                    ("growth", "wacc cases"),
                    ("growth", "wacc", "cases"),
                ),
            ),
            (
                "base-case marker",
                (
                    ("base", "$", "adjusted enterprise value"),
                    ("base", "$", "sensitivity"),
                ),
            ),
            (
                "quantified spread endpoints",
                (
                    ("$", "downside", "upside"),
                    ("$", "range", "sensitivity"),
                    ("$", "base", "growth", "wacc"),
                ),
            ),
        ),
    ),
    (
        "Financial trend visual",
        (
            "Financial Performance detailed schedule",
            "Year ending March",
            "08 Historical Ratio Analysis",
            "Margin and growth at a glance",
        ),
        (
            (
                "uploaded-financials premise",
                (
                    ("revenue", "ebitda trend", "uploaded-financials schedule"),
                    ("revenue", "ebitda trend", "uploaded financials schedule"),
                    ("revenue and ebitda trend", "uploaded-financials schedule"),
                    ("revenue and ebitda trend", "uploaded financials schedule"),
                ),
            ),
            (
                "period coverage",
                (
                    ("fy23 actual", "fy25 actual", "fy26 forecast"),
                    ("fy23", "fy25", "fy26 forecast"),
                ),
            ),
            (
                "revenue series",
                (
                    ("revenue", "$980,000", "$1,350,000"),
                    ("revenue", "$1,250,000", "$1,350,000"),
                ),
            ),
            (
                "EBITDA series",
                (
                    ("ebitda", "$165,000", "$259,000"),
                    ("ebitda", "$240,000", "$259,000"),
                ),
            ),
            (
                "EBITDA margin context",
                (
                    ("ebitda margin", "16.8%", "19.2%"),
                    ("ebitda margin", "18.5%", "19.2%"),
                ),
            ),
        ),
    ),
    (
        "Valuation approach selection",
        (
            "07 Financial Performance",
            "Trading performance at a glance",
            "Financial trend visual",
        ),
        (
            (
                "approach-selection premise",
                (
                    ("adopts dcf", "market multiples", "cross-check", "net-asset method"),
                    ("adopts dcf", "market multiples", "cross-check", "net asset method"),
                    ("dcf", "market multiples", "cross-check", "net-asset method"),
                ),
            ),
            (
                "income approach adopted as primary",
                (
                    ("income approach", "dcf", "adopted as primary", "going-concern sme"),
                    ("income approach", "dcf", "adopted as primary", "maintainable free cash flow"),
                ),
            ),
            (
                "market approach cross-check only",
                (
                    ("market approach", "ev/ebitda", "reasonableness cross-check", "not applied mechanically"),
                    ("market approach", "ev/ebitda", "reasonableness cross-check", "scale", "liquidity"),
                    ("market approach", "ev/ebitda", "cross-check range", "5.0x", "7.0x"),
                ),
            ),
            (
                "asset approach not primary",
                (
                    ("asset approach", "net assets", "not primary", "going concern"),
                    ("asset approach", "net assets", "not primary", "liquidation"),
                    ("asset approach", "net assets", "enterprise-to-equity bridge", "$"),
                ),
            ),
        ),
    ),
    (
        "Implied multiple reconciliation",
        (
            "Multiples Cross-check detailed schedule",
            "Input Low Mid High",
            "16 Sensitivity and Specific Risks",
            "Sensitivity spread visual",
        ),
        (
            (
                "DCF-versus-market premise",
                (
                    ("primary dcf output", "researched ev/ebitda cross-check range"),
                    ("primary dcf output", "researched ev/ebitda", "cross-check"),
                    ("primary dcf", "market", "ev/ebitda", "cross-check"),
                ),
            ),
            (
                "normalised EBITDA basis",
                (
                    ("normalised ebitda", "$", "maintainable earnings base"),
                    ("normalised ebitda", "$", "market and dcf implied multiple checks"),
                    ("normalised ebitda", "$", "dcf implied multiple checks"),
                ),
            ),
            (
                "market multiple cross-check range",
                (
                    ("market ev/ebitda range", "5.0x", "7.0x", "reasonableness cross-check"),
                    ("market ev/ebitda range", "researched market range", "reasonableness cross-check"),
                ),
            ),
            (
                "DCF post-illiquidity range",
                (
                    ("dcf post-illiquidity range", "6.6x", "9.9x", "adjusted enterprise-value"),
                    ("dcf post-illiquidity range", "primary dcf", "ev/ebitda multiple"),
                    ("dcf post illiquidity range", "primary dcf", "ev/ebitda multiple"),
                ),
            ),
            (
                "DCF pre-illiquidity range",
                (
                    ("dcf pre-illiquidity range", "7.5x", "11.2x", "marketability discount"),
                    ("dcf pre-illiquidity range", "enterprise-value range", "private-company"),
                    ("dcf pre illiquidity range", "marketability discount"),
                ),
            ),
            (
                "DCF midpoint multiple",
                (
                    ("dcf midpoint multiple", "8.1x", "normalised ebitda"),
                    ("dcf midpoint multiple", "adjusted dcf enterprise value", "normalised ebitda"),
                ),
            ),
            (
                "cross-check tension",
                (
                    ("cross-check tension", "above market midpoint"),
                    ("cross-check tension", "below market midpoint"),
                    ("selected dcf midpoint", "above", "market midpoint"),
                    ("selected dcf midpoint", "below", "market midpoint"),
                ),
            ),
        ),
    ),
)
_GENERIC_SOURCE_SUPPORT_VALUES = {
    "source",
    "sources",
    "source url",
    "url",
    "website",
    "public source",
    "online source",
    "general source",
    "general reference",
    "reference",
    "references",
    "supporting source",
    "supporting evidence",
    "n/a",
    "na",
    "not applicable",
    "not specified",
}
_SOURCE_SUPPORT_USE_MARKERS = (
    "benchmark",
    "beta",
    "cash",
    "company",
    "comparable",
    "context",
    "corroboration",
    "customer",
    "discount",
    "evidence",
    "equity",
    "financial",
    "growth",
    "inflation",
    "interest",
    "market",
    "multiple",
    "profile",
    "premium",
    "public",
    "rate",
    "revenue",
    "risk",
    "sector",
    "terminal",
    "valuation",
    "wacc",
)


@dataclass(frozen=True)
class ReportQualityIssue:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class ReportQualityAudit:
    artifact: str
    issues: tuple[ReportQualityIssue, ...]
    metadata: dict[str, Any]

    @property
    def passed(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact": self.artifact,
            "passed": self.passed,
            "issues": [issue.as_dict() for issue in self.issues],
            "metadata": self.metadata,
        }


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")


def _all_report_text(content: dict) -> str:
    return _json_text(content)


def _report_narrative_blocks(content: dict) -> list[tuple[str, str]]:
    """Return report narrative blocks where repeated prose is most visible."""
    if not isinstance(content, dict):
        return []
    blocks: list[tuple[str, str]] = []
    for section, value in content.items():
        if isinstance(value, str):
            blocks.append((section, value))
        elif isinstance(value, dict) and isinstance(value.get("narrative"), str):
            blocks.append((section, value["narrative"]))
    return blocks


def _normalise_repeat_segment(segment: object) -> str:
    """Normalise narrative text enough to compare adjacent duplicate lines/sentences."""
    text = html_lib.unescape(str(segment or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", text)
    text = re.sub(r"^#+\s*", "", text)
    text = " ".join(text.split()).strip(" .;:-").lower()
    return text


def _adjacent_duplicate_lines(text: object, *, min_chars: int = 45) -> list[str]:
    """Return repeated adjacent narrative lines after ignoring blank lines."""
    duplicates: list[str] = []
    previous_normalised = ""
    for raw_line in str(text or "").splitlines():
        display = " ".join(raw_line.split()).strip()
        normalised = _normalise_repeat_segment(raw_line)
        if len(normalised) < min_chars:
            continue
        if normalised == previous_normalised:
            duplicates.append(display[:180])
        previous_normalised = normalised
    return duplicates


def _adjacent_duplicate_sentences(text: object, *, min_chars: int = 55) -> list[str]:
    """Return repeated adjacent visible sentences in rendered artifacts."""
    visible = " ".join(str(text or "").split())
    duplicates: list[str] = []
    previous_normalised = ""
    for sentence in re.split(r"(?<=[.!?])\s+", visible):
        display = sentence.strip()
        normalised = _normalise_repeat_segment(display)
        if len(normalised) < min_chars:
            continue
        if normalised == previous_normalised:
            duplicates.append(display[:180])
        previous_normalised = normalised
    return duplicates


def _issue(code: str, message: str) -> ReportQualityIssue:
    return ReportQualityIssue(code=code, message=message)


def _has_all_markers(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return all(marker.lower() in lowered for marker in markers)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def _url_count(value: object) -> int:
    return len(set(match.rstrip(").,;]") for match in _URL_RE.findall(_json_text(value))))


def _urls(value: object) -> list[str]:
    return [match.rstrip(").,;]") for match in _URL_RE.findall(_json_text(value))]


def _is_non_public_url(url: str, *, require_public_hostname: bool = True) -> bool:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return True
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    if ip and (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    return require_public_hostname and "." not in host


def _non_public_urls(value: object, *, require_public_hostname: bool = True) -> list[str]:
    return [
        url
        for url in _urls(value)
        if _is_non_public_url(url, require_public_hostname=require_public_hostname)
    ]


def _safe_external_source_link_count(html: str) -> int:
    """Return safe external source anchors in rendered browser report HTML."""
    return len(_SAFE_EXTERNAL_SOURCE_LINK_RE.findall(str(html or "")))


def _table_rows_missing_urls(section: object) -> list[int]:
    """Return 1-based table row numbers that do not contain a URL."""
    if not isinstance(section, dict):
        return []
    table = section.get("table")
    if not isinstance(table, dict):
        return []
    rows = table.get("rows")
    if not isinstance(rows, list):
        return []
    return [
        index
        for index, row in enumerate(rows, start=1)
        if _url_count(row) == 0
    ]


def _source_rows_with_thin_support(section: object) -> list[int]:
    """Return source-table row numbers whose support/use description is too generic."""
    if not isinstance(section, dict):
        return []
    table = section.get("table")
    if not isinstance(table, dict):
        return []
    rows = table.get("rows")
    if not isinstance(rows, list):
        return []

    headers = table.get("headers")
    support_index = None
    if isinstance(headers, list):
        for index, header in enumerate(headers):
            header_text = str(header or "").lower()
            if any(marker in header_text for marker in ("support", "used for", "description", "why")):
                support_index = index
                break
    if support_index is None:
        support_index = 2

    thin_rows: list[int] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, (list, tuple)) or len(row) <= support_index:
            thin_rows.append(index)
            continue
        support_text = " ".join(str(row[support_index] or "").split())
        support_lower = support_text.lower().strip(" .:;-")
        words = re.findall(r"[a-z0-9]+", support_lower)
        if (
            support_lower in _GENERIC_SOURCE_SUPPORT_VALUES
            or len(words) < 3
            or not any(marker in support_lower for marker in _SOURCE_SUPPORT_USE_MARKERS)
        ):
            thin_rows.append(index)

    return thin_rows


def _thin_source_support_artifact_snippets(text: str) -> list[str]:
    """Return rendered source rows whose support/use text after a URL is too generic."""
    normalised = " ".join(str(text or "").split())
    if not normalised:
        return []

    snippets: list[str] = []
    urls = _urls(normalised)
    for url in urls:
        start = normalised.find(url)
        if start < 0:
            continue
        support_start = start + len(url)
        next_url_positions = [
            index
            for other_url in urls
            if other_url != url and (index := normalised.find(other_url, support_start)) > support_start
        ]
        end = min(next_url_positions) if next_url_positions else min(len(normalised), support_start + 160)
        support_text = normalised[support_start:end].strip(" .:;-")
        support_lower = support_text.lower()
        words = re.findall(r"[a-z0-9]+", support_lower)
        first_one = " ".join(words[:1])
        first_two = " ".join(words[:2])
        first_three = " ".join(words[:3])
        if (
            first_one in _GENERIC_SOURCE_SUPPORT_VALUES
            or first_two in _GENERIC_SOURCE_SUPPORT_VALUES
            or first_three in _GENERIC_SOURCE_SUPPORT_VALUES
        ):
            snippets.append(f"{url} -> {support_text[:80] or '(blank)'}")
    return snippets


def _valuation_numbered_section_markers() -> tuple[str, ...]:
    """Return expected numbered valuation section headings for artifact audits."""
    return tuple(
        f"{index:02d} {_VALUATION_SECTION_TITLES.get(key, key.replace('_', ' ').title())}"
        for index, key in enumerate(SECTION_SCHEMAS["valuation_advisory"], start=1)
    )


def _numbered_section_order_issues(text: str) -> list[str]:
    """Return issues when numbered report sections are present but out of order."""
    lowered = " ".join(str(text or "").split()).lower()
    marker_positions = [
        (
            marker,
            [match.start() for match in re.finditer(re.escape(marker.lower()), lowered)],
        )
        for marker in _valuation_numbered_section_markers()
    ]
    issues: list[str] = []

    def check_order(label: str, indexed_positions: list[tuple[str, int]]) -> None:
        if len(indexed_positions) < 2:
            return
        previous_marker, previous_position = indexed_positions[0]
        for marker, position in indexed_positions[1:]:
            if position <= previous_position:
                issues.append(
                    f"{label} section order breaks at {marker}; it appears before {previous_marker}."
                )
                return
            previous_marker, previous_position = marker, position

    check_order(
        "Contents",
        [(marker, positions[0]) for marker, positions in marker_positions if positions],
    )
    check_order(
        "Body",
        [(marker, positions[-1]) for marker, positions in marker_positions if len(positions) >= 2],
    )
    return issues


def _missing_scope_exclusion_concepts(text: str) -> list[str]:
    """Return required scope-exclusion concepts not visible in artifact text."""
    normalised = " ".join(str(text or "").split())
    lowered_all = normalised.lower()
    start = lowered_all.find("scope exclusions")
    if start >= 0:
        end_candidates = [
            index
            for marker in (
                "management input trail",
                "management input - valuation purpose",
                "evidence and model basis",
            )
            if (index := lowered_all.find(marker, start + len("scope exclusions"))) > start
        ]
        end = min(end_candidates) if end_candidates else start + 1200
        lowered = lowered_all[start:end]
    else:
        lowered = lowered_all
    return [
        concept
        for concept, required_groups in _SCOPE_EXCLUSION_CONCEPTS.items()
        if not all(any(marker in lowered for marker in alternatives) for alternatives in required_groups)
    ]


def _missing_derived_technical_assumption_concepts(text: str) -> list[str]:
    """Return technical assumptions not covered in the derived-assumptions row."""
    normalised = " ".join(str(text or "").split())
    lowered_all = normalised.lower()
    start = lowered_all.find("derived technical assumptions")
    if start >= 0:
        end_candidates = [
            index
            for marker in (
                "01 introduction",
                "accountiq indicative valuation",
                "public research and source trail",
                "simulated public research",
            )
            if (index := lowered_all.find(marker, start + len("derived technical assumptions"))) > start
        ]
        end = min(end_candidates) if end_candidates else start + 900
        lowered = lowered_all[start:end]
    else:
        lowered = ""
    return [
        concept
        for concept, required_groups in _TECHNICAL_ASSUMPTION_EXCLUSION_CONCEPTS.items()
        if not all(any(marker in lowered for marker in alternatives) for alternatives in required_groups)
    ]


def _missing_management_input_trail_detail(text: str) -> list[str]:
    """Return management-input rows whose report-use rationale is missing or thin."""
    normalised = " ".join(str(text or "").split())
    lowered_all = normalised.lower()
    label_order = [label for label, _required_groups in _MANAGEMENT_INPUT_TRAIL_DETAIL_CONCEPTS]
    missing: list[str] = []

    for label, required_groups in _MANAGEMENT_INPUT_TRAIL_DETAIL_CONCEPTS:
        start = _find_management_input_marker(lowered_all, label)
        if start < 0:
            continue

        end_candidates = [
            index
            for next_label in label_order
            if next_label != label
            and (index := _find_management_input_marker(lowered_all, next_label, start + 1)) > start
        ]
        end_candidates.extend(
            index
            for boundary in (
                "evidence and model basis",
                "derived technical assumptions",
                "01 introduction",
            )
            if (index := lowered_all.find(boundary, start + 1)) > start
        )
        end = min(end_candidates) if end_candidates else start + 900
        row_text = lowered_all[start:end]
        missing_concepts = [
            concept
            for concept, alternatives in required_groups
            if not any(marker in row_text for marker in alternatives)
        ]
        if "management-confirmed private input" not in row_text:
            missing_concepts.append("management-confirmed private input basis")
        if missing_concepts:
            missing.append(f"{label}: {', '.join(missing_concepts)}")

    return missing


def _find_management_input_marker(text: str, label: str, start: int = 0) -> int:
    """Return a management-input label position, tolerating PDF table extraction splits."""
    lowered = str(text or "").lower()
    label_lower = str(label or "").lower()
    exact_marker = f"{_MANAGEMENT_INPUT_MARKER_PREFIX.lower()}{label_lower}"
    exact_index = lowered.find(exact_marker, start)
    if exact_index >= 0:
        return exact_index

    words = re.findall(r"[a-z0-9]+", label_lower)
    if len(words) < 2:
        return -1
    leading_pattern = r"[\s-]+".join(re.escape(word) for word in words[:-1])
    final_word = re.escape(words[-1])
    pattern = re.compile(
        rf"{re.escape(_MANAGEMENT_INPUT_MARKER_PREFIX.lower())}"
        rf"{leading_pattern}.{{0,260}}?{final_word}"
    )
    match = pattern.search(lowered, start)
    return match.start() if match else -1


def _front_matter_structure_issues(text: str) -> list[str]:
    """Return issues when valuation front matter reads like a merged table."""
    normalised = " ".join(str(text or "").split())
    lowered = normalised.lower()
    positions = {
        "report letter": lowered.find("report letter"),
        "scope exclusions": lowered.find("scope exclusions"),
        "management input trail": lowered.find("management input trail"),
        "evidence and model basis": lowered.find("evidence and model basis"),
        "derived technical assumptions": lowered.find("derived technical assumptions"),
        "questions intentionally not asked": lowered.find("questions intentionally not asked"),
    }
    issues: list[str] = [
        f"missing {label}"
        for label, index in positions.items()
        if index < 0
    ]
    if issues:
        return issues

    if not (
        positions["report letter"]
        < positions["scope exclusions"]
        < positions["management input trail"]
        < positions["evidence and model basis"]
        < positions["derived technical assumptions"]
        < positions["questions intentionally not asked"]
    ):
        issues.append(
            "front matter should read as report letter, scope exclusions, management input trail, "
            "evidence/model basis, derived technical assumptions, then questions intentionally not asked"
        )

    introduction = lowered.find("01 introduction", positions["scope exclusions"])
    if introduction >= 0 and positions["questions intentionally not asked"] > introduction:
        issues.append("basis of preparation details should appear before section 01")

    management_input_start = positions["management input trail"]
    evidence_start = positions["evidence and model basis"]
    for marker in _PDF_MANAGEMENT_INPUT_TRAIL_MARKERS:
        label = marker.removeprefix(_MANAGEMENT_INPUT_MARKER_PREFIX)
        marker_index = _find_management_input_marker(lowered, label)
        if marker_index >= 0 and not management_input_start < marker_index < evidence_start:
            issues.append(
                f"{marker} should sit inside the management input trail before evidence/model basis"
            )

    return issues


def _missing_source_hierarchy_concepts(text: str) -> list[str]:
    """Return source hierarchy concepts not visible in a rendered artifact."""
    lowered = " ".join(str(text or "").split()).lower()
    return [
        concept
        for concept, required_groups in _SOURCE_HIERARCHY_CONCEPTS.items()
        if not all(any(marker in lowered for marker in alternatives) for alternatives in required_groups)
    ]


def _section_window_text(text: str, start_marker: str, end_markers: tuple[str, ...]) -> str:
    """Return the last matching section window from flattened artifact text."""
    normalised = " ".join(str(text or "").split())
    lowered = normalised.lower()
    start = lowered.rfind(start_marker.lower())
    if start < 0:
        return ""
    end_candidates = [
        index
        for marker in end_markers
        if (index := lowered.find(marker.lower(), start + len(start_marker))) > start
    ]
    end = min(end_candidates) if end_candidates else len(normalised)
    return normalised[start:end]


def _missing_comparable_caveat_concepts(text: str) -> list[str]:
    """Return missing comparability-caveat concepts for market evidence."""
    lowered = " ".join(str(text or "").split()).lower()
    missing: list[str] = []
    if not any(marker in lowered for marker in _COMPARABLE_CAVEAT_ROLE_MARKERS):
        missing.append("reasonableness cross-check role")
    if not any(marker in lowered for marker in _COMPARABLE_CAVEAT_LIMITATION_MARKERS):
        missing.append("not-directly-comparable limitation")
    return missing


def _missing_interpretation_panel_concepts(text: str) -> list[str]:
    """Return interpretation panels that are present as headings but too thin."""
    normalised = " ".join(str(text or "").split())
    missing: list[str] = []
    for panel_title, end_markers, required_concepts in _INTERPRETATION_PANEL_CONCEPTS:
        panel_text = _section_window_text(normalised, panel_title, end_markers)
        if not panel_text:
            continue
        lowered = panel_text.lower()
        for concept, alternatives in required_concepts:
            if not any(all(marker in lowered for marker in group) for group in alternatives):
                missing.append(f"{panel_title}: {concept}")
    return missing


def _missing_at_a_glance_panel_concepts(text: str) -> list[str]:
    """Return required source/reliance glance panels that are present but too thin."""
    normalised = " ".join(str(text or "").split())
    missing: list[str] = []
    for panel_title, end_markers, required_concepts in _AT_A_GLANCE_PANEL_CONCEPTS:
        panel_text = _section_window_text(normalised, panel_title, end_markers)
        if not panel_text:
            continue
        lowered = panel_text.lower()
        for concept, alternatives in required_concepts:
            if not any(all(marker in lowered for marker in group) for group in alternatives):
                missing.append(f"{panel_title}: {concept}")
    return missing


def _missing_visual_panel_concepts(text: str) -> list[str]:
    """Return required valuation visuals that are present but too thin."""
    normalised = " ".join(str(text or "").split())
    missing: list[str] = []
    for panel_title, end_markers, required_concepts in _VISUAL_PANEL_CONCEPTS:
        panel_text = _section_window_text(normalised, panel_title, end_markers)
        if not panel_text:
            continue
        lowered = panel_text.lower()
        for concept, alternatives in required_concepts:
            if not any(all(marker in lowered for marker in group) for group in alternatives):
                missing.append(f"{panel_title}: {concept}")
    return missing


def _revenue_outlook_consistency_issues(text: str) -> list[str]:
    """Return report-visible conflicts between the management-input trail and valuation sections."""
    lowered = " ".join(str(text or "").split()).lower()
    if not any(marker in lowered for marker in _NOT_SURE_REVENUE_OUTLOOK_MARKERS):
        return []
    return [
        marker
        for marker in _MODEST_GROWTH_OUTLOOK_MARKERS
        if marker in lowered
    ]


def _content_revenue_outlook_consistency_issues(content: dict) -> list[str]:
    """Return structured-content conflicts between not-sure outlook and modest-growth treatment."""
    assumptions = content.get("valuation_assumptions") if isinstance(content, dict) else None
    table = assumptions.get("table") if isinstance(assumptions, dict) else None
    rows = table.get("rows") if isinstance(table, dict) else None
    if not isinstance(rows, list):
        return []

    has_not_sure_outlook = False
    for row in rows:
        if not isinstance(row, list) or not row:
            continue
        label = " ".join(str(row[0] or "").split()).lower()
        row_text = " ".join(str(cell or "") for cell in row).lower()
        if label == "revenue outlook" and (
            "not sure - growth derived from uploaded financial history" in row_text
            or "no specific forecast provided; growth derived from uploaded financial history" in row_text
        ):
            has_not_sure_outlook = True
            break
    if not has_not_sure_outlook:
        return []

    lowered = " ".join(_all_report_text(content).split()).lower()
    return [
        marker
        for marker in _MODEST_GROWTH_OUTLOOK_MARKERS
        if marker in lowered
    ]


def _html_visible_text(html: str) -> str:
    """Return a lightweight visible-text approximation for generated report HTML audits."""
    without_style = re.sub(r"<style\b[^>]*>.*?</style>", " ", str(html or ""), flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_style)
    return html_lib.unescape(" ".join(without_tags.split()))


def _html_cover_text(html: str) -> str:
    """Return visible text from the report cover, excluding later body sections."""
    raw = str(html or "")
    lowered = raw.lower()
    start_candidates = [
        index
        for marker in ('<section class="cover"', "<section class='cover'")
        if (index := lowered.find(marker)) >= 0
    ]
    start = min(start_candidates) if start_candidates else 0
    end_candidates = [
        index
        for marker in ('<section class="report-page contents"', "<section class='report-page contents'")
        if (index := lowered.find(marker, start)) > start
    ]
    end = min(end_candidates) if end_candidates else len(raw)
    return " ".join(_html_visible_text(raw[start:end]).split())


def _html_cover_snapshot_text(html: str) -> str:
    """Return visible text from the cover valuation snapshot only."""
    raw = str(html or "")
    lowered = raw.lower()
    start_candidates = [
        index
        for marker in ('<aside class="cover-snapshot"', "<aside class='cover-snapshot'")
        if (index := lowered.find(marker)) >= 0
    ]
    if not start_candidates:
        return ""
    start = min(start_candidates)
    end = lowered.find("</aside>", start)
    if end < 0:
        end = len(raw)
    else:
        end += len("</aside>")
    return " ".join(_html_visible_text(raw[start:end]).split())


def _html_cover_report_basis_text(html: str) -> str:
    """Return visible text from the cover report-basis strip only."""
    raw = str(html or "")
    lowered = raw.lower()
    start_candidates = [
        index
        for marker in ('<aside class="cover-report-basis"', "<aside class='cover-report-basis'")
        if (index := lowered.find(marker)) >= 0
    ]
    if not start_candidates:
        return ""
    start = min(start_candidates)
    end = lowered.find("</aside>", start)
    if end < 0:
        end = len(raw)
    else:
        end += len("</aside>")
    return " ".join(_html_visible_text(raw[start:end]).split())


def _pdf_cover_text(text: str) -> str:
    """Return the likely PDF cover text before report navigation/body text begins."""
    normalised = " ".join(str(text or "").split())
    lowered = normalised.lower()
    end_candidates = [
        index
        for marker in ("report navigation", "contents", "basis of preparation", "01 introduction")
        if (index := lowered.find(marker)) > 0
    ]
    end = min(end_candidates) if end_candidates else min(len(normalised), 1800)
    return normalised[:end]


def _pdf_cover_snapshot_text(text: str) -> str:
    """Return the likely PDF cover valuation-snapshot text."""
    normalised = " ".join(str(text or "").split())
    lowered = normalised.lower()
    start = lowered.find("valuation snapshot")
    if start < 0:
        return ""
    end_candidates = [
        index
        for marker in (
            "computed from",
            "demo data - not for reliance",
            "confidential - indicative only",
            "prepared for",
            "report navigation",
            "contents",
        )
        if (index := lowered.find(marker, start + len("valuation snapshot"))) > start
    ]
    end = min(end_candidates) if end_candidates else min(len(normalised), start + 1200)
    return normalised[start:end]


def _money_value_count(text: object) -> int:
    """Return visible dollar-value tokens in report text."""
    return len(_MONEY_VALUE_RE.findall(str(text or "")))


def _cover_snapshot_row_value_issues(text: object) -> list[str]:
    """Return cover snapshot rows that do not carry high/mid/low dollar values."""
    normalised = " ".join(str(text or "").split())
    lowered = normalised.lower()
    row_specs = (
        ("Enterprise value", ("enterprise value",), ("less: net debt", "less net debt", "net debt", "indicative equity value")),
        ("Net debt", ("less: net debt", "less net debt", "net debt"), ("indicative equity value",)),
        ("Indicative equity value", ("indicative equity value",), ("computed from", "prepared for", "demo data", "confidential", "report navigation", "contents")),
    )
    issues: list[str] = []
    for label, label_markers, next_markers in row_specs:
        starts = [
            index
            for marker in label_markers
            if (index := lowered.find(marker)) >= 0
        ]
        if not starts:
            issues.append(f"{label}: missing row")
            continue
        start = min(starts)
        ends = [
            index
            for marker in next_markers
            if (index := lowered.find(marker, start + 1)) > start
        ]
        end = min(ends) if ends else len(normalised)
        row_text = normalised[start:end]
        row_lowered = row_text.lower()
        missing_value_positions = [
            index
            for marker in _COVER_SNAPSHOT_MISSING_VALUE_MARKERS
            if (index := row_lowered.find(marker)) >= 0
        ]
        if missing_value_positions:
            first_missing_value = min(missing_value_positions)
            row_text = row_text[:first_missing_value]
        value_count = _money_value_count(row_text)
        if value_count < 3:
            issues.append(f"{label}: {value_count} dollar values")
    return issues


def audit_valuation_report_content(content: dict) -> ReportQualityAudit:
    """Audit structured valuation-report JSON for professional-pack completeness."""
    issues: list[ReportQualityIssue] = []
    expected_sections = SECTION_SCHEMAS["valuation_advisory"]

    if not isinstance(content, dict):
        return ReportQualityAudit(
            artifact="valuation_report_content",
            issues=(_issue("content_not_object", "Report content must be a JSON object."),),
            metadata={"section_count": 0},
        )

    missing = [section for section in expected_sections if section not in content]
    unexpected = [section for section in content if section not in expected_sections]
    if missing:
        issues.append(_issue("missing_sections", f"Missing required valuation sections: {missing}"))
    if unexpected:
        issues.append(_issue("unexpected_sections", f"Unexpected valuation sections present: {unexpected}"))

    section_count = len([section for section in expected_sections if section in content])
    if section_count < len(expected_sections):
        issues.append(
            _issue(
                "thin_section_count",
                f"Only {section_count} of {len(expected_sections)} valuation sections are present.",
            )
        )

    table_sections = set(TABLE_SECTIONS_VALUATION)
    table_section_count = 0
    for section in expected_sections:
        value = content.get(section)
        if section in table_sections:
            if isinstance(value, dict) and isinstance(value.get("table"), dict):
                table_section_count += 1
                rows = value["table"].get("rows")
                if not isinstance(rows, list) or not rows:
                    issues.append(_issue("empty_table", f"Section '{section}' has no table rows."))
            else:
                issues.append(_issue("missing_table", f"Section '{section}' must include narrative and table data."))

    if table_section_count < len(table_sections):
        issues.append(
            _issue(
                "thin_table_count",
                f"Only {table_section_count} of {len(table_sections)} table sections include tables.",
            )
        )

    text = _all_report_text(content)
    lowered = text.lower()
    leaked_markers = [marker for marker in _IMPLEMENTATION_MARKERS if marker in lowered]
    if leaked_markers:
        issues.append(_issue("implementation_language", f"Client-facing implementation terms found: {leaked_markers}"))
    leaked_internal_keys = [marker for marker in _INTERNAL_VALUATION_KEY_MARKERS if marker in lowered]
    if leaked_internal_keys:
        issues.append(
            _issue(
                "internal_valuation_key_language",
                "Report should use reader-facing labels, not raw valuation source keys: "
                f"{leaked_internal_keys}",
            )
        )
    leaked_intake_keys = [marker for marker in _RAW_VALUATION_INTAKE_KEY_MARKERS if marker in lowered]
    if leaked_intake_keys:
        issues.append(
            _issue(
                "raw_valuation_intake_key_language",
                "Report should use reader-facing labels, not raw valuation intake field or option keys: "
                f"{leaked_intake_keys}",
            )
        )
    placeholder_markers = [marker for marker in _PLACEHOLDER_MARKERS if marker in lowered]
    if placeholder_markers:
        issues.append(_issue("placeholder_text", f"Placeholder or failed-generation text found: {placeholder_markers}"))
    draft_language_markers = [marker for marker in _DRAFT_LANGUAGE_MARKERS if marker in lowered]
    if draft_language_markers:
        issues.append(
            _issue(
                "draft_language",
                "Report should read as a polished professional pack, not a draft artifact: "
                f"{draft_language_markers}",
            )
        )
    legacy_owner_markers = [marker for marker in _LEGACY_OWNER_DEPENDENCY_MARKERS if marker in lowered]
    if legacy_owner_markers:
        issues.append(
            _issue(
                "legacy_owner_dependency_language",
                "Report should use owner or key-person dependency wording consistently: "
                f"{legacy_owner_markers}",
            )
        )
    legacy_private_context_markers = [marker for marker in _LEGACY_PRIVATE_CONTEXT_MARKERS if marker in lowered]
    if legacy_private_context_markers:
        issues.append(
            _issue(
                "legacy_private_context_language",
                "Report should use private valuation context wording for optional private notes: "
                f"{legacy_private_context_markers}",
            )
        )
    sale_process_risk_markers = [marker for marker in _SALE_PROCESS_RISK_MARKERS if marker in lowered]
    if sale_process_risk_markers:
        issues.append(
            _issue(
                "sale_process_risk_language",
                "Report risk language should be purpose-neutral rather than sale-process specific: "
                f"{sale_process_risk_markers}",
            )
        )
    unfinished_markers = [marker for marker in UNFINISHED_FOLLOWUP_MARKERS if marker in lowered]
    if unfinished_markers:
        issues.append(
            _issue(
                "unfinished_followup_language",
                "Report reads like an unfinished questionnaire or follow-up request: "
                f"{unfinished_markers}",
            )
        )
    repeated_narrative_lines = [
        f"{section}: {line}"
        for section, block in _report_narrative_blocks(content)
        for line in _adjacent_duplicate_lines(block)
    ]
    if repeated_narrative_lines:
        issues.append(
            _issue(
                "repeated_narrative_line",
                "Report narrative contains repeated adjacent prose that reads like a draft artifact: "
                f"{repeated_narrative_lines}",
            )
        )
    revenue_outlook_conflicts = _content_revenue_outlook_consistency_issues(content)
    if revenue_outlook_conflicts:
        issues.append(
            _issue(
                "content_revenue_outlook_inconsistency",
                "Report content says no specific revenue forecast was provided but later treats it as modest growth: "
                f"{revenue_outlook_conflicts}",
            )
        )

    required_professional_markers = {
        "valuation_methods": ("discounted cash flow", "market", "multiple"),
        "valuation_outputs": ("enterprise value", "equity value", "valuation range"),
        "cash_flow_model": ("wacc", "terminal growth", "free cash flow"),
        "risk_and_sensitivity": ("sensitivity", "key-person", "customer concentration"),
        "reliance_and_compliance": ("indicative", "financial advice", "fmca", "relied"),
        "source_hierarchy": ("uploaded financial", "management-confirmed", "public research"),
    }
    for code, markers in required_professional_markers.items():
        if not _has_all_markers(text, markers):
            issues.append(_issue(f"missing_{code}", f"Report text does not cover required markers: {markers}"))

    executive_summary = content.get("executive_summary")
    summary_rows = (
        executive_summary.get("table", {}).get("rows", [])
        if isinstance(executive_summary, dict)
        else []
    )
    summary_text = _json_text(summary_rows).lower()
    if not all(marker in summary_text for marker in ("enterprise value", "indicative equity value")):
        issues.append(
            _issue(
                "missing_valuation_snapshot_rows",
                "Executive summary table must include enterprise value and indicative equity value rows.",
            )
        )

    dcf_analysis = content.get("dcf_analysis")
    cash_flow_schedule = (
        dcf_analysis.get("cash_flow_schedule")
        if isinstance(dcf_analysis, dict)
        else None
    )
    if not isinstance(cash_flow_schedule, dict) or not cash_flow_schedule.get("rows"):
        issues.append(
            _issue(
                "missing_cash_flow_schedule",
                "DCF analysis must include the mid-case forecast cash-flow schedule.",
            )
        )
    else:
        cash_flow_row_labels = {
            str(row[0] or "").strip().lower()
            for row in cash_flow_schedule.get("rows") or []
            if isinstance(row, list) and row
        }
        missing_cash_flow_rows = [
            label
            for label in _CASH_FLOW_SCHEDULE_ROW_LABELS
            if label.lower() not in cash_flow_row_labels
        ]
        if missing_cash_flow_rows:
            issues.append(
                _issue(
                    "incomplete_cash_flow_schedule",
                    "DCF analysis mid-case forecast cash-flow schedule is missing required rows: "
                    f"{missing_cash_flow_rows}",
                )
            )

    risks = content.get("sensitivity_and_risks")
    risk_table = (
        risks.get("specific_risk_factors")
        if isinstance(risks, dict)
        else None
    )
    if not isinstance(risk_table, dict) or len(risk_table.get("rows") or []) < 4:
        issues.append(
            _issue(
                "missing_specific_risk_factors",
                "Sensitivity section must include the specific risk-factor table from the five management inputs.",
            )
        )

    source_url_count = _url_count(content.get("sources"))
    comparable_url_count = _url_count(content.get("comparable_evidence"))
    source_rows_missing_urls = _table_rows_missing_urls(content.get("sources"))
    source_rows_with_thin_support = _source_rows_with_thin_support(content.get("sources"))
    comparable_rows_missing_urls = _table_rows_missing_urls(content.get("comparable_evidence"))
    comparable_caveat_missing = _missing_comparable_caveat_concepts(
        _all_report_text(content.get("comparable_evidence"))
    )
    non_public_source_urls = sorted(
        set(_non_public_urls(content.get("sources")) + _non_public_urls(content.get("comparable_evidence")))
    )
    if source_url_count < 2:
        issues.append(_issue("thin_source_trail", "Sources section should include at least two public source URLs."))
    if source_rows_missing_urls:
        issues.append(
            _issue(
                "source_rows_missing_urls",
                "Every sources table row should include its supporting public source URL. "
                f"Missing rows: {source_rows_missing_urls}",
            )
        )
    if source_rows_with_thin_support:
        issues.append(
            _issue(
                "source_rows_thin_support",
                "Every sources table row should explain what the source supports or is used for. "
                f"Thin rows: {source_rows_with_thin_support}",
            )
        )
    if comparable_url_count < 1:
        issues.append(_issue("missing_comparable_urls", "Comparable evidence should include source URLs."))
    if comparable_rows_missing_urls:
        issues.append(
            _issue(
                "comparable_rows_missing_urls",
                "Every comparable-evidence table row should include its supporting public source URL. "
                f"Missing rows: {comparable_rows_missing_urls}",
            )
        )
    if comparable_caveat_missing:
        issues.append(
            _issue(
                "missing_comparable_caveat",
                "Comparable evidence must be framed as a reasonableness cross-check with limitations, not direct private-company pricing: "
                f"{comparable_caveat_missing}",
            )
        )
    if non_public_source_urls:
        issues.append(
            _issue(
                "non_public_source_urls",
                "Source trail should only retain public HTTP(S) URLs, not localhost, private-network or internal links: "
                f"{non_public_source_urls}",
            )
        )

    return ReportQualityAudit(
        artifact="valuation_report_content",
        issues=tuple(issues),
        metadata={
            "section_count": section_count,
            "expected_section_count": len(expected_sections),
            "table_section_count": table_section_count,
            "source_url_count": source_url_count,
            "source_rows_missing_url_count": len(source_rows_missing_urls),
            "source_rows_thin_support_count": len(source_rows_with_thin_support),
            "comparable_url_count": comparable_url_count,
            "comparable_rows_missing_url_count": len(comparable_rows_missing_urls),
            "comparable_caveat_missing": comparable_caveat_missing,
            "non_public_source_url_count": len(non_public_source_urls),
        },
    )


def audit_valuation_report_html(html: str, *, demo_mode: bool) -> ReportQualityAudit:
    """Audit rendered browser valuation-report HTML for professional-pack presentation."""
    issues: list[ReportQualityIssue] = []
    raw_html = str(html or "")
    visible_text = _html_visible_text(raw_html)
    cover_text = _html_cover_text(raw_html)
    cover_report_basis_text = _html_cover_report_basis_text(raw_html)
    cover_snapshot_text = _html_cover_snapshot_text(raw_html)
    normalised = " ".join(visible_text.split())
    lowered = normalised.lower()
    cover_lowered = cover_text.lower()
    cover_report_basis_lowered = cover_report_basis_text.lower()
    cover_snapshot_lowered = cover_snapshot_text.lower()
    raw_lowered = raw_html.lower()

    required_cover_markers = (
        "Prepared for",
        "Prepared by",
        "Report type",
        "Reference",
        "Valuation date",
        "Purpose",
        "Basis of value",
        "Reliance",
    )
    for marker in required_cover_markers:
        if marker.lower() not in cover_lowered:
            issues.append(_issue("missing_html_cover_marker", f"Browser report cover is missing marker: {marker}"))

    if (
        'class="cover-report-basis"' not in raw_lowered
        or 'aria-label="report basis"' not in raw_lowered
        or "report basis" not in cover_report_basis_lowered
    ):
        issues.append(
            _issue(
                "missing_html_cover_report_basis",
                "Browser report cover must include the compact report-basis strip linking uploaded financials, private inputs, public sources and the AccountIQ model.",
            )
        )
    elif missing_cover_report_basis_markers := [
        marker
        for marker in _COVER_REPORT_BASIS_MARKERS
        if marker.lower() not in cover_report_basis_lowered
    ]:
        issues.append(
            _issue(
                "missing_html_cover_report_basis",
                "Browser report cover report-basis strip is missing required markers: "
                f"{missing_cover_report_basis_markers}",
            )
        )

    for marker in _PROFESSIONAL_REPORT_MARKERS:
        if marker.lower() not in lowered:
            issues.append(_issue("missing_html_marker", f"Browser report HTML is missing marker: {marker}"))
    for marker in _valuation_numbered_section_markers():
        marker_count = lowered.count(marker.lower())
        if marker_count == 0:
            issues.append(
                _issue(
                    "missing_html_numbered_section",
                    f"Browser report HTML is missing numbered section heading: {marker}",
                )
            )
        elif marker_count < 2:
            issues.append(
                _issue(
                    "html_numbered_section_mismatch",
                    "Browser report HTML should show each numbered section in both contents and body: "
                    f"{marker}",
                )
            )
    for order_issue in _numbered_section_order_issues(normalised):
        issues.append(
            _issue(
                "html_numbered_section_order",
                f"Browser report numbered sections are out of order: {order_issue}",
            )
        )
    missing_scope_exclusions = _missing_scope_exclusion_concepts(normalised)
    if missing_scope_exclusions:
        issues.append(
            _issue(
                "missing_html_scope_exclusions",
                "Browser report front matter must state scope exclusions for: "
                f"{missing_scope_exclusions}",
            )
        )
    missing_technical_exclusions = _missing_derived_technical_assumption_concepts(normalised)
    if missing_technical_exclusions:
        issues.append(
            _issue(
                "missing_html_derived_technical_assumption_detail",
                "Browser report front matter must state derived technical assumptions for: "
                f"{missing_technical_exclusions}",
            )
        )

    missing_management_input_markers = [
        marker
        for marker in _PDF_MANAGEMENT_INPUT_TRAIL_MARKERS
        if _find_management_input_marker(
            lowered,
            marker.removeprefix(_MANAGEMENT_INPUT_MARKER_PREFIX),
        )
        < 0
    ]
    if missing_management_input_markers:
        issues.append(
            _issue(
                "missing_html_management_input_trail",
                "Browser report basis of preparation is missing the management input trail: "
                f"{missing_management_input_markers}",
            )
        )
    missing_management_input_detail = _missing_management_input_trail_detail(normalised)
    if missing_management_input_detail:
        issues.append(
            _issue(
                "incomplete_html_management_input_trail_detail",
                "Browser report management input trail must explain how each short answer informs the report: "
                f"{missing_management_input_detail}",
            )
        )
    front_matter_structure_issues = _front_matter_structure_issues(normalised)
    if front_matter_structure_issues:
        issues.append(
            _issue(
                "html_front_matter_structure",
                "Browser report basis of preparation should keep scope, management inputs and evidence/model basis separate: "
                f"{front_matter_structure_issues}",
            )
        )
    missing_source_hierarchy = _missing_source_hierarchy_concepts(normalised)
    if missing_source_hierarchy:
        issues.append(
            _issue(
                "missing_html_source_hierarchy",
                "Browser report should distinguish uploaded financials, management-confirmed inputs, public research and AccountIQ calculations: "
                f"{missing_source_hierarchy}",
            )
        )
    html_comparable_caveat_missing = _missing_comparable_caveat_concepts(
        _section_window_text(
            normalised,
            "17 Comparable Evidence Appendix",
            ("18 Sources and References", "19 Disclaimer"),
        )
    )
    if html_comparable_caveat_missing:
        issues.append(
            _issue(
                "missing_html_comparable_caveat",
                "Browser report comparable evidence must be framed as a reasonableness cross-check with limitations, not direct private-company pricing: "
                f"{html_comparable_caveat_missing}",
            )
        )
    missing_interpretation_panels = _missing_interpretation_panel_concepts(normalised)
    if missing_interpretation_panels:
        issues.append(
            _issue(
                "incomplete_html_interpretation_panels",
                "Browser report interpretation panels must explain how WACC and market evidence affect the valuation, not just show headings: "
                f"{missing_interpretation_panels}",
            )
        )
    missing_glance_panels = _missing_at_a_glance_panel_concepts(normalised)
    if missing_glance_panels:
        issues.append(
            _issue(
                "incomplete_html_glance_panels",
                "Browser report source and reliance at-a-glance panels must explain the evidence and reliance basis, not just show headings: "
                f"{missing_glance_panels}",
            )
        )
    missing_visual_panels = _missing_visual_panel_concepts(normalised)
    if missing_visual_panels:
        issues.append(
            _issue(
                "incomplete_html_visual_panels",
                "Browser report valuation visuals must show the key rows, midpoint markers and range context, not just show headings: "
                f"{missing_visual_panels}",
            )
        )
    revenue_outlook_conflicts = _revenue_outlook_consistency_issues(normalised)
    if revenue_outlook_conflicts:
        issues.append(
            _issue(
                "html_revenue_outlook_inconsistency",
                "Browser report says no specific revenue forecast was provided but later treats it as modest growth: "
                f"{revenue_outlook_conflicts}",
            )
        )

    if "<script" in raw_lowered:
        issues.append(_issue("html_script_tag", "Browser report HTML must not include script tags."))
    if "javascript:" in raw_lowered or "onerror=" in raw_lowered or "onclick=" in raw_lowered:
        issues.append(_issue("html_unsafe_markup", "Browser report HTML contains unsafe inline markup."))

    artifact_markers = [marker for marker in _HTML_LAYOUT_ARTIFACTS if marker in normalised]
    if artifact_markers:
        issues.append(_issue("html_layout_artifact", f"Browser report text contains layout/glyph artifacts: {artifact_markers}"))

    leaked_markers = [marker for marker in _IMPLEMENTATION_MARKERS if marker in lowered]
    if leaked_markers:
        issues.append(_issue("html_implementation_language", f"Browser report contains implementation terms: {leaked_markers}"))
    leaked_internal_keys = [marker for marker in _INTERNAL_VALUATION_KEY_MARKERS if marker in lowered]
    if leaked_internal_keys:
        issues.append(
            _issue(
                "html_internal_valuation_key_language",
                "Browser report should use reader-facing labels, not raw valuation source keys: "
                f"{leaked_internal_keys}",
            )
        )
    leaked_intake_keys = [marker for marker in _RAW_VALUATION_INTAKE_KEY_MARKERS if marker in lowered]
    if leaked_intake_keys:
        issues.append(
            _issue(
                "html_raw_valuation_intake_key_language",
                "Browser report should use reader-facing labels, not raw valuation intake field or option keys: "
                f"{leaked_intake_keys}",
            )
        )
    placeholder_markers = [marker for marker in _PLACEHOLDER_MARKERS if marker in lowered]
    if placeholder_markers:
        issues.append(_issue("html_placeholder_text", f"Browser report contains placeholder text: {placeholder_markers}"))
    draft_language_markers = [marker for marker in _DRAFT_LANGUAGE_MARKERS if marker in lowered]
    if draft_language_markers:
        issues.append(
            _issue(
                "html_draft_language",
                "Browser report should read as a polished professional pack, not a draft artifact: "
                f"{draft_language_markers}",
            )
        )
    legacy_owner_markers = [marker for marker in _LEGACY_OWNER_DEPENDENCY_MARKERS if marker in lowered]
    if legacy_owner_markers:
        issues.append(
            _issue(
                "html_legacy_owner_dependency_language",
                "Browser report should use owner or key-person dependency wording consistently: "
                f"{legacy_owner_markers}",
            )
        )
    legacy_private_context_markers = [marker for marker in _LEGACY_PRIVATE_CONTEXT_MARKERS if marker in lowered]
    if legacy_private_context_markers:
        issues.append(
            _issue(
                "html_legacy_private_context_language",
                "Browser report should use private valuation context wording for optional private notes: "
                f"{legacy_private_context_markers}",
            )
        )
    sale_process_risk_markers = [marker for marker in _SALE_PROCESS_RISK_MARKERS if marker in lowered]
    if sale_process_risk_markers:
        issues.append(
            _issue(
                "html_sale_process_risk_language",
                "Browser report risk language should be purpose-neutral rather than sale-process specific: "
                f"{sale_process_risk_markers}",
            )
        )
    unfinished_markers = [marker for marker in UNFINISHED_FOLLOWUP_MARKERS if marker in lowered]
    if unfinished_markers:
        issues.append(
            _issue(
                "html_unfinished_followup_language",
                "Browser report reads like an unfinished questionnaire or follow-up request: "
                f"{unfinished_markers}",
            )
        )
    repeated_sentences = _adjacent_duplicate_sentences(normalised)
    if repeated_sentences:
        issues.append(
            _issue(
                "html_repeated_narrative_sentence",
                "Browser report contains repeated adjacent prose that reads like a draft artifact: "
                f"{repeated_sentences}",
            )
        )

    if _url_count(raw_html) < 2:
        issues.append(_issue("html_thin_source_trail", "Browser report should include at least two public source URLs."))
    html_source_trail_text = " ".join(
        filter(
            None,
            (
                _section_window_text(
                    normalised,
                    "17 Comparable Evidence Appendix",
                    ("18 Sources and References", "19 Disclaimer"),
                ),
                _section_window_text(
                    normalised,
                    "18 Sources and References",
                    ("19 Disclaimer", "20 General Principles"),
                ),
            ),
        )
    )
    html_non_public_urls = sorted(set(_non_public_urls(html_source_trail_text)))
    if html_non_public_urls:
        issues.append(
            _issue(
                "html_non_public_source_urls",
                "Browser report source trail should only retain public HTTP(S) URLs, not localhost, private-network or internal links: "
                f"{html_non_public_urls}",
            )
        )
    html_thin_source_support = _thin_source_support_artifact_snippets(html_source_trail_text)
    if html_thin_source_support:
        issues.append(
            _issue(
                "html_source_rows_thin_support",
                "Browser report source rows should explain what each retained URL supports, not use generic labels: "
                f"{html_thin_source_support}",
            )
        )
    if _safe_external_source_link_count(raw_html) < 2:
        issues.append(
            _issue(
                "html_source_links_not_clickable",
                "Browser report should render retained public source URLs as safe clickable links.",
            )
        )

    if 'class="cover"' not in raw_lowered:
        issues.append(_issue("missing_html_cover_page", "Browser report is missing the professional cover page."))
    if (
        'class="cover-snapshot"' not in raw_lowered
        or 'aria-label="valuation snapshot"' not in raw_lowered
        or "valuation snapshot" not in cover_snapshot_lowered
    ):
        issues.append(
            _issue(
                "missing_html_cover_snapshot",
                "Browser report cover must include the compact valuation snapshot sourced from the computed valuation table.",
            )
        )
    missing_html_cover_snapshot_markers = [
        marker
        for marker in _COVER_SNAPSHOT_MARKERS
        if marker.lower() not in cover_snapshot_lowered
    ]
    if missing_html_cover_snapshot_markers:
        issues.append(
            _issue(
                "missing_html_cover_snapshot",
                "Browser report cover must include the compact valuation snapshot sourced from the computed valuation table: "
                f"{missing_html_cover_snapshot_markers}",
            )
        )
    html_cover_snapshot_value_count = _money_value_count(cover_snapshot_text)
    if html_cover_snapshot_value_count < 9:
        issues.append(
            _issue(
                "thin_html_cover_snapshot_values",
                "Browser report cover valuation snapshot must show high/mid/low figures for enterprise value, net debt and equity value. "
                f"Found {html_cover_snapshot_value_count} dollar values.",
            )
        )
    html_cover_snapshot_row_issues = _cover_snapshot_row_value_issues(cover_snapshot_text)
    if html_cover_snapshot_row_issues:
        issues.append(
            _issue(
                "incomplete_html_cover_snapshot_rows",
                "Browser report cover valuation snapshot must show three dollar values in each required row: "
                f"{html_cover_snapshot_row_issues}",
            )
        )
    if 'class="report-page contents"' not in raw_lowered:
        issues.append(_issue("missing_html_contents_page", "Browser report is missing the contents page."))
    if 'id="basis-of-preparation"' not in raw_lowered:
        issues.append(_issue("missing_html_basis_page", "Browser report is missing the basis-of-preparation front matter."))
    if 'href="./pdf"' not in raw_lowered:
        issues.append(_issue("missing_html_pdf_download", "Browser report is missing the PDF download action."))

    demo_label = "demo data - not for reliance"
    if demo_mode and demo_label not in lowered:
        issues.append(_issue("missing_html_demo_label", "Demo browser report must be unmistakably labelled as demo data."))
    if demo_mode and "demo data only - not for reliance" not in lowered:
        issues.append(_issue("missing_html_demo_cover_reliance", "Demo browser report cover must repeat that it is not for reliance."))
    if not demo_mode and demo_label in lowered:
        issues.append(_issue("unexpected_html_demo_label", "Live/customer browser report must not be labelled as demo data."))
    live_demo_language_markers = [marker for marker in _LIVE_DEMO_LANGUAGE_MARKERS if marker in lowered]
    if not demo_mode and live_demo_language_markers:
        issues.append(
            _issue(
                "html_demo_language_in_live_report",
                "Live/customer browser report must not contain demo, simulated or sample-report language: "
                f"{live_demo_language_markers}",
            )
        )
    if not demo_mode and not _has_all_markers(
        normalised,
        ("Indicative valuation support only", "independent professional advice"),
    ):
        issues.append(
            _issue(
                "missing_html_live_cover_reliance",
                "Live/customer browser report cover must include indicative-valuation support and independent-advice reliance wording.",
            )
        )

    return ReportQualityAudit(
        artifact="valuation_report_html",
        issues=tuple(issues),
        metadata={
            "url_count": _url_count(raw_html),
            "non_public_source_url_count": len(html_non_public_urls),
            "demo_mode": demo_mode,
            "text_length": len(normalised),
        },
    )


def audit_valuation_pdf_text(
    text: str,
    *,
    page_count: int,
    demo_mode: bool,
    cover_text: str | None = None,
) -> ReportQualityAudit:
    """Audit extracted valuation PDF text for professional pack presentation."""
    issues: list[ReportQualityIssue] = []
    normalised = " ".join(str(text or "").split())
    lowered = normalised.lower()
    cover_normalised = " ".join(str(cover_text if cover_text is not None else _pdf_cover_text(normalised)).split())
    cover_lowered = cover_normalised.lower()
    cover_snapshot_normalised = _pdf_cover_snapshot_text(cover_normalised)
    cover_snapshot_lowered = cover_snapshot_normalised.lower()

    if page_count < 20:
        issues.append(
            _issue(
                "thin_pdf_page_count",
                f"PDF has {page_count} pages; expected a full professional valuation pack.",
            )
        )

    required_pdf_markers = (
        "VALUATION SNAPSHOT",
        "Contents",
        "Basis of preparation",
        "Report letter",
        "Prepared for",
        "Prepared by",
        "Preparer role",
        "Report channel",
        "Purpose and reliance",
        "Important limitation",
        "Information basis",
        "Scope exclusions",
        "Management input trail",
        "Evidence and model basis",
        "Derived technical assumptions",
        "Questions intentionally not asked",
        "01 Introduction",
        "02 Executive Summary",
        "Valuation conclusion at a glance",
        "Valuation range visual",
        "Business context at a glance",
        "Market context at a glance",
        "Methodology at a glance",
        "Trading performance at a glance",
        "Financial trend visual",
        "Margin and growth at a glance",
        "Normalisation impact at a glance",
        "Normalised EBITDA bridge",
        "How the discount rate drives the range",
        "WACC build visual",
        "Enterprise-to-equity bridge",
        "Enterprise-to-equity visual",
        "Valuation approach selection",
        "How the market cross-check is used",
        "Implied multiple reconciliation",
        "11 Valuation Approach and Assumptions",
        "Assumption basis at a glance",
        "13 Discounted Cash Flow Analysis",
        "DCF value build visual",
        "DCF forecast bridge at a glance",
        "Valuation range at a glance",
        "16 Sensitivity and Specific Risks",
        "Sensitivity spread visual",
        "Sensitivity takeaway at a glance",
        "18 Sources and References",
        "Comparable evidence at a glance",
        "Source trail at a glance",
        "19 Disclaimer",
        "Reliance at a glance",
        "20 General Principles",
        "21 Glossary",
        "Mid-case forecast cash-flow schedule",
        "Specific risk factors",
    )
    for marker in required_pdf_markers:
        if marker.lower() not in lowered:
            issues.append(_issue("missing_pdf_marker", f"PDF text is missing marker: {marker}"))
    for marker in _valuation_numbered_section_markers():
        marker_count = lowered.count(marker.lower())
        if marker_count == 0:
            issues.append(
                _issue(
                    "missing_pdf_numbered_section",
                    f"PDF text is missing numbered section heading: {marker}",
                )
            )
        elif marker_count < 2:
            issues.append(
                _issue(
                    "pdf_numbered_section_mismatch",
                    "PDF should show each numbered section in both contents and body text: "
                    f"{marker}",
                )
            )
    for order_issue in _numbered_section_order_issues(normalised):
        issues.append(
            _issue(
                "pdf_numbered_section_order",
                f"PDF numbered sections are out of order: {order_issue}",
            )
        )
    missing_scope_exclusions = _missing_scope_exclusion_concepts(normalised)
    if missing_scope_exclusions:
        issues.append(
            _issue(
                "missing_pdf_scope_exclusions",
                "PDF basis of preparation must state scope exclusions for: "
                f"{missing_scope_exclusions}",
            )
        )
    missing_technical_exclusions = _missing_derived_technical_assumption_concepts(normalised)
    if missing_technical_exclusions:
        issues.append(
            _issue(
                "missing_pdf_derived_technical_assumption_detail",
                "PDF basis of preparation must state derived technical assumptions for: "
                f"{missing_technical_exclusions}",
            )
        )

    required_cover_markers = (
        "PREPARED FOR",
        "PREPARED BY",
        "REPORT TYPE",
        "REFERENCE",
        "VALUATION DATE",
        "PURPOSE",
        "BASIS OF VALUE",
        "RELIANCE",
    )
    for marker in required_cover_markers:
        if marker.lower() not in cover_lowered:
            issues.append(_issue("missing_pdf_cover_marker", f"PDF cover is missing marker: {marker}"))

    missing_cover_report_basis_markers = [
        marker
        for marker in _COVER_REPORT_BASIS_MARKERS
        if marker.lower() not in cover_lowered
    ]
    if missing_cover_report_basis_markers:
        issues.append(
            _issue(
                "missing_pdf_cover_report_basis",
                "PDF cover must include the compact report-basis strip linking uploaded financials, private inputs, public sources and the AccountIQ model: "
                f"{missing_cover_report_basis_markers}",
            )
        )

    missing_cover_snapshot_markers = [
        marker
        for marker in _COVER_SNAPSHOT_MARKERS
        if marker.lower() not in cover_snapshot_lowered
    ]
    if missing_cover_snapshot_markers:
        issues.append(
            _issue(
                "missing_pdf_cover_snapshot",
                "PDF cover must include the compact valuation snapshot sourced from the computed valuation table: "
                f"{missing_cover_snapshot_markers}",
            )
        )
    pdf_cover_snapshot_value_count = _money_value_count(cover_snapshot_normalised)
    if pdf_cover_snapshot_value_count < 9:
        issues.append(
            _issue(
                "thin_pdf_cover_snapshot_values",
                "PDF cover valuation snapshot must show high/mid/low figures for enterprise value, net debt and equity value. "
                f"Found {pdf_cover_snapshot_value_count} dollar values.",
            )
        )
    pdf_cover_snapshot_row_issues = _cover_snapshot_row_value_issues(cover_snapshot_normalised)
    if pdf_cover_snapshot_row_issues:
        issues.append(
            _issue(
                "incomplete_pdf_cover_snapshot_rows",
                "PDF cover valuation snapshot must show three dollar values in each required row: "
                f"{pdf_cover_snapshot_row_issues}",
            )
        )

    missing_management_input_markers = [
        marker
        for marker in _PDF_MANAGEMENT_INPUT_TRAIL_MARKERS
        if _find_management_input_marker(
            lowered,
            marker.removeprefix(_MANAGEMENT_INPUT_MARKER_PREFIX),
        )
        < 0
    ]
    if missing_management_input_markers:
        issues.append(
            _issue(
                "missing_pdf_management_input_trail",
                "PDF basis of preparation is missing the management input trail: "
                f"{missing_management_input_markers}",
            )
        )
    missing_management_input_detail = _missing_management_input_trail_detail(normalised)
    if missing_management_input_detail:
        issues.append(
            _issue(
                "incomplete_pdf_management_input_trail_detail",
                "PDF management input trail must explain how each short answer informs the report: "
                f"{missing_management_input_detail}",
            )
        )
    front_matter_structure_issues = _front_matter_structure_issues(normalised)
    if front_matter_structure_issues:
        issues.append(
            _issue(
                "pdf_front_matter_structure",
                "PDF basis of preparation should keep scope, management inputs and evidence/model basis separate: "
                f"{front_matter_structure_issues}",
            )
        )
    missing_source_hierarchy = _missing_source_hierarchy_concepts(normalised)
    if missing_source_hierarchy:
        issues.append(
            _issue(
                "missing_pdf_source_hierarchy",
                "PDF should distinguish uploaded financials, management-confirmed inputs, public research and AccountIQ calculations: "
                f"{missing_source_hierarchy}",
            )
        )
    pdf_comparable_caveat_missing = _missing_comparable_caveat_concepts(
        _section_window_text(
            normalised,
            "17 Comparable Evidence Appendix",
            ("18 Sources and References", "19 Disclaimer"),
        )
    )
    if pdf_comparable_caveat_missing:
        issues.append(
            _issue(
                "missing_pdf_comparable_caveat",
                "PDF comparable evidence must be framed as a reasonableness cross-check with limitations, not direct private-company pricing: "
                f"{pdf_comparable_caveat_missing}",
            )
        )
    missing_interpretation_panels = _missing_interpretation_panel_concepts(normalised)
    if missing_interpretation_panels:
        issues.append(
            _issue(
                "incomplete_pdf_interpretation_panels",
                "PDF interpretation panels must explain how WACC and market evidence affect the valuation, not just show headings: "
                f"{missing_interpretation_panels}",
            )
        )
    missing_glance_panels = _missing_at_a_glance_panel_concepts(normalised)
    if missing_glance_panels:
        issues.append(
            _issue(
                "incomplete_pdf_glance_panels",
                "PDF source and reliance at-a-glance panels must explain the evidence and reliance basis, not just show headings: "
                f"{missing_glance_panels}",
            )
        )
    missing_visual_panels = _missing_visual_panel_concepts(normalised)
    if missing_visual_panels:
        issues.append(
            _issue(
                "incomplete_pdf_visual_panels",
                "PDF valuation visuals must show the key rows, midpoint markers and range context, not just show headings: "
                f"{missing_visual_panels}",
            )
        )
    revenue_outlook_conflicts = _revenue_outlook_consistency_issues(normalised)
    if revenue_outlook_conflicts:
        issues.append(
            _issue(
                "pdf_revenue_outlook_inconsistency",
                "PDF says no specific revenue forecast was provided but later treats it as modest growth: "
                f"{revenue_outlook_conflicts}",
            )
        )

    artifact_markers = [marker for marker in _UNICODE_LAYOUT_ARTIFACTS if marker in normalised]
    if artifact_markers:
        issues.append(_issue("pdf_layout_artifact", f"PDF text contains layout/glyph artifacts: {artifact_markers}"))

    leaked_markers = [marker for marker in _IMPLEMENTATION_MARKERS if marker in lowered]
    if leaked_markers:
        issues.append(_issue("pdf_implementation_language", f"PDF contains implementation terms: {leaked_markers}"))
    leaked_internal_keys = [marker for marker in _INTERNAL_VALUATION_KEY_MARKERS if marker in lowered]
    if leaked_internal_keys:
        issues.append(
            _issue(
                "pdf_internal_valuation_key_language",
                "PDF should use reader-facing labels, not raw valuation source keys: "
                f"{leaked_internal_keys}",
            )
        )
    leaked_intake_keys = [marker for marker in _RAW_VALUATION_INTAKE_KEY_MARKERS if marker in lowered]
    if leaked_intake_keys:
        issues.append(
            _issue(
                "pdf_raw_valuation_intake_key_language",
                "PDF should use reader-facing labels, not raw valuation intake field or option keys: "
                f"{leaked_intake_keys}",
            )
        )
    placeholder_markers = [marker for marker in _PLACEHOLDER_MARKERS if marker in lowered]
    if placeholder_markers:
        issues.append(_issue("pdf_placeholder_text", f"PDF contains placeholder text: {placeholder_markers}"))
    draft_language_markers = [marker for marker in _DRAFT_LANGUAGE_MARKERS if marker in lowered]
    if draft_language_markers:
        issues.append(
            _issue(
                "pdf_draft_language",
                "PDF should read as a polished professional pack, not a draft artifact: "
                f"{draft_language_markers}",
            )
        )
    legacy_owner_markers = [marker for marker in _LEGACY_OWNER_DEPENDENCY_MARKERS if marker in lowered]
    if legacy_owner_markers:
        issues.append(
            _issue(
                "pdf_legacy_owner_dependency_language",
                "PDF should use owner or key-person dependency wording consistently: "
                f"{legacy_owner_markers}",
            )
        )
    legacy_private_context_markers = [marker for marker in _LEGACY_PRIVATE_CONTEXT_MARKERS if marker in lowered]
    if legacy_private_context_markers:
        issues.append(
            _issue(
                "pdf_legacy_private_context_language",
                "PDF should use private valuation context wording for optional private notes: "
                f"{legacy_private_context_markers}",
            )
        )
    sale_process_risk_markers = [marker for marker in _SALE_PROCESS_RISK_MARKERS if marker in lowered]
    if sale_process_risk_markers:
        issues.append(
            _issue(
                "pdf_sale_process_risk_language",
                "PDF risk language should be purpose-neutral rather than sale-process specific: "
                f"{sale_process_risk_markers}",
            )
        )
    unfinished_markers = [marker for marker in UNFINISHED_FOLLOWUP_MARKERS if marker in lowered]
    if unfinished_markers:
        issues.append(
            _issue(
                "pdf_unfinished_followup_language",
                "PDF reads like an unfinished questionnaire or follow-up request: "
                f"{unfinished_markers}",
            )
        )
    repeated_sentences = _adjacent_duplicate_lines(text) + _adjacent_duplicate_sentences(normalised)
    if repeated_sentences:
        issues.append(
            _issue(
                "pdf_repeated_narrative_sentence",
                "PDF contains repeated adjacent prose that reads like a draft artifact: "
                f"{repeated_sentences}",
            )
        )

    demo_label = "DEMO DATA - NOT FOR RELIANCE"
    if demo_mode and demo_label not in normalised:
        issues.append(_issue("missing_demo_label", "Demo PDF must be unmistakably labelled as demo data."))
    if demo_mode and "demo data only - not for reliance" not in cover_lowered:
        issues.append(_issue("missing_demo_cover_reliance", "Demo PDF cover must repeat that it is not for reliance."))
    if not demo_mode and demo_label in normalised:
        issues.append(_issue("unexpected_demo_label", "Live/customer PDF must not be labelled as demo data."))
    live_demo_language_markers = [marker for marker in _LIVE_DEMO_LANGUAGE_MARKERS if marker in lowered]
    if not demo_mode and live_demo_language_markers:
        issues.append(
            _issue(
                "pdf_demo_language_in_live_report",
                "Live/customer PDF must not contain demo, simulated or sample-report language: "
                f"{live_demo_language_markers}",
            )
        )
    if not demo_mode and not _has_all_markers(
        cover_normalised,
        ("Indicative valuation support only", "independent professional advice"),
    ):
        issues.append(
            _issue(
                "missing_live_cover_reliance",
                "Live/customer PDF cover must include indicative-valuation support and independent-advice reliance wording.",
            )
        )

    if _url_count(normalised) < 2:
        issues.append(_issue("pdf_thin_source_trail", "PDF should include at least two public source URLs."))
    pdf_non_public_urls = sorted(set(_non_public_urls(normalised, require_public_hostname=False)))
    if pdf_non_public_urls:
        issues.append(
            _issue(
                "pdf_non_public_source_urls",
                "PDF source trail should only retain public HTTP(S) URLs, not localhost, private-network or internal links: "
                f"{pdf_non_public_urls}",
            )
        )
    pdf_source_trail_text = _section_window_text(
        normalised,
        "18 Sources and References",
        ("19 Disclaimer", "20 General Principles"),
    )
    pdf_thin_source_support = _thin_source_support_artifact_snippets(pdf_source_trail_text)
    if pdf_thin_source_support:
        issues.append(
            _issue(
                "pdf_source_rows_thin_support",
                "PDF source rows should explain what each retained URL supports, not use generic labels: "
                f"{pdf_thin_source_support}",
            )
        )

    return ReportQualityAudit(
        artifact="valuation_report_pdf",
        issues=tuple(issues),
        metadata={
            "page_count": page_count,
            "url_count": _url_count(normalised),
            "non_public_source_url_count": len(pdf_non_public_urls),
            "demo_mode": demo_mode,
        },
    )


def audit_valuation_report_pdf(pdf_path: Path, *, demo_mode: bool) -> ReportQualityAudit:
    """Extract and audit text from a valuation PDF artifact."""
    import pdfplumber

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return ReportQualityAudit(
            artifact="valuation_report_pdf",
            issues=(_issue("pdf_missing", f"PDF file does not exist: {pdf_path}"),),
            metadata={"page_count": 0, "url_count": 0, "demo_mode": demo_mode},
        )
    if not pdf_path.read_bytes().startswith(b"%PDF-"):
        return ReportQualityAudit(
            artifact="valuation_report_pdf",
            issues=(_issue("pdf_invalid_header", f"File does not look like a PDF: {pdf_path}"),),
            metadata={"page_count": 0, "url_count": 0, "demo_mode": demo_mode},
        )

    with pdfplumber.open(pdf_path) as pdf:
        page_texts = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(page_texts)
        page_count = len(pdf.pages)

    audit = audit_valuation_pdf_text(
        text,
        page_count=page_count,
        demo_mode=demo_mode,
        cover_text=page_texts[0] if page_texts else "",
    )
    issues = list(audit.issues)
    metadata = dict(audit.metadata)
    demo_label = "DEMO DATA - NOT FOR RELIANCE"
    if demo_mode:
        missing_demo_label_pages = [
            index
            for index, page_text in enumerate(page_texts, start=1)
            if demo_label not in page_text
        ]
        metadata["demo_labelled_page_count"] = page_count - len(missing_demo_label_pages)
        if missing_demo_label_pages:
            issues.append(
                _issue(
                    "missing_demo_label_pages",
                    "Demo PDF must repeat the not-for-reliance label on every page. "
                    f"Missing pages: {missing_demo_label_pages}",
                )
            )

    return ReportQualityAudit(
        artifact=audit.artifact,
        issues=tuple(issues),
        metadata=metadata,
    )


def _credit_numbered_section_markers() -> tuple[str, ...]:
    """Return expected numbered section headings for credit-paper audits."""
    return tuple(
        f"{index:02d} {_CREDIT_SECTION_TITLES.get(key, key.replace('_', ' ').title())}"
        for index, key in enumerate(SECTION_SCHEMAS["bank_credit_paper"], start=1)
    )


def _credit_numbered_section_order_issues(text: str) -> list[str]:
    """Return issues when credit-paper sections appear out of order."""
    lowered = " ".join(str(text or "").split()).lower()
    marker_positions = [
        (
            marker,
            [match.start() for match in re.finditer(re.escape(marker.lower()), lowered)],
        )
        for marker in _credit_numbered_section_markers()
    ]
    issues: list[str] = []

    def check_order(label: str, indexed_positions: list[tuple[str, int]]) -> None:
        if len(indexed_positions) < 2:
            return
        previous_marker, previous_position = indexed_positions[0]
        for marker, position in indexed_positions[1:]:
            if position <= previous_position:
                issues.append(
                    f"{label} section order breaks at {marker}; it appears before {previous_marker}."
                )
                return
            previous_marker, previous_position = marker, position

    check_order(
        "Contents",
        [(marker, positions[0]) for marker, positions in marker_positions if positions],
    )
    check_order(
        "Body",
        [(marker, positions[-1]) for marker, positions in marker_positions if len(positions) >= 2],
    )
    return issues


def _credit_artifact_text_issues(
    text: str,
    *,
    cover_text: str,
    demo_mode: bool,
    artifact_label: str,
) -> list[ReportQualityIssue]:
    """Apply report-type-specific checks shared by HTML and PDF credit outputs."""
    normalised = " ".join(str(text or "").split())
    lowered = normalised.lower()
    cover_lowered = " ".join(str(cover_text or "").split()).lower()
    issues: list[ReportQualityIssue] = []

    for marker in _CREDIT_REQUIRED_COVER_MARKERS:
        if marker.lower() not in cover_lowered:
            issues.append(
                _issue(
                    f"missing_{artifact_label}_credit_cover_marker",
                    f"{artifact_label.upper()} credit-paper cover is missing marker: {marker}",
                )
            )
    missing_body_markers = [
        marker for marker in _CREDIT_REQUIRED_BODY_MARKERS if marker.lower() not in lowered
    ]
    if missing_body_markers:
        issues.append(
            _issue(
                f"missing_{artifact_label}_credit_marker",
                f"{artifact_label.upper()} credit paper is missing lender-output markers: {missing_body_markers}",
            )
        )

    for marker in _credit_numbered_section_markers():
        marker_count = lowered.count(marker.lower())
        if marker_count == 0:
            issues.append(
                _issue(
                    f"missing_{artifact_label}_credit_section",
                    f"{artifact_label.upper()} credit paper is missing numbered section heading: {marker}",
                )
            )
        elif marker_count < 2:
            issues.append(
                _issue(
                    f"{artifact_label}_credit_section_mismatch",
                    f"{artifact_label.upper()} credit paper should show each numbered section in contents and body: {marker}",
                )
            )
    for order_issue in _credit_numbered_section_order_issues(normalised):
        issues.append(
            _issue(
                f"{artifact_label}_credit_section_order",
                f"{artifact_label.upper()} credit-paper sections are out of order: {order_issue}",
            )
        )

    valuation_only_markers = [
        marker for marker in _CREDIT_VALUATION_ONLY_MARKERS if marker.lower() in lowered
    ]
    if valuation_only_markers:
        issues.append(
            _issue(
                f"{artifact_label}_credit_valuation_language",
                f"{artifact_label.upper()} credit paper contains valuation-only framing: {valuation_only_markers}",
            )
        )

    layout_artifacts = [marker for marker in _UNICODE_LAYOUT_ARTIFACTS if marker in normalised]
    if layout_artifacts:
        issues.append(
            _issue(
                f"{artifact_label}_credit_layout_artifact",
                f"{artifact_label.upper()} credit paper contains layout/glyph artifacts: {layout_artifacts}",
            )
        )
    placeholder_markers = [marker for marker in _CREDIT_PLACEHOLDER_MARKERS if marker in lowered]
    if placeholder_markers:
        issues.append(
            _issue(
                f"{artifact_label}_credit_placeholder_text",
                f"{artifact_label.upper()} credit paper contains placeholder text: {placeholder_markers}",
            )
        )
    draft_language_markers = [marker for marker in _DRAFT_LANGUAGE_MARKERS if marker in lowered]
    if draft_language_markers:
        issues.append(
            _issue(
                f"{artifact_label}_credit_draft_language",
                f"{artifact_label.upper()} credit paper reads like a draft artifact: {draft_language_markers}",
            )
        )
    if demo_mode and "demo data - not for reliance" not in lowered:
        issues.append(
            _issue(
                f"missing_{artifact_label}_credit_demo_label",
                f"Demo {artifact_label.upper()} credit paper must be labelled as not for reliance.",
            )
        )
    if not demo_mode and "demo data - not for reliance" in lowered:
        issues.append(
            _issue(
                f"unexpected_{artifact_label}_credit_demo_label",
                f"Live {artifact_label.upper()} credit paper must not be labelled as demo data.",
            )
        )
    return issues


def audit_bank_credit_report_html(html: str, *, demo_mode: bool) -> ReportQualityAudit:
    """Audit rendered browser Bank Credit Paper HTML for lender-pack presentation."""
    raw_html = str(html or "")
    visible_text = _html_visible_text(raw_html)
    cover_text = _html_cover_text(raw_html)
    cover_basis_text = _html_cover_report_basis_text(raw_html)
    normalised = " ".join(visible_text.split())
    raw_lowered = raw_html.lower()
    issues = _credit_artifact_text_issues(
        normalised,
        cover_text=cover_text,
        demo_mode=demo_mode,
        artifact_label="html",
    )
    cover_basis_lowered = cover_basis_text.lower()
    missing_basis_markers = [
        marker
        for marker in _CREDIT_REQUIRED_BASIS_MARKERS
        if marker.lower() not in cover_basis_lowered
        and not (
            marker == "Debt-capacity model"
            and "credit model" in cover_basis_lowered
        )
    ]
    if (
        'class="cover-report-basis"' not in raw_lowered
        or 'aria-label="report basis"' not in raw_lowered
        or missing_basis_markers
    ):
        issues.append(
            _issue(
                "missing_html_credit_report_basis",
                "Browser credit-paper cover must include the lender report-basis strip with: "
                f"{missing_basis_markers or list(_CREDIT_REQUIRED_BASIS_MARKERS)}",
            )
        )
    if 'class="cover"' not in raw_lowered:
        issues.append(_issue("missing_html_credit_cover_page", "Browser credit paper is missing the cover page."))
    if 'class="report-page contents"' not in raw_lowered:
        issues.append(_issue("missing_html_credit_contents_page", "Browser credit paper is missing the contents page."))
    if 'href="./pdf"' not in raw_lowered and "href='./pdf'" not in raw_lowered:
        issues.append(_issue("missing_html_credit_pdf_download", "Browser credit paper is missing the PDF download action."))
    if "<script" in raw_lowered or "javascript:" in raw_lowered or "onerror=" in raw_lowered or "onclick=" in raw_lowered:
        issues.append(_issue("html_credit_unsafe_markup", "Browser credit paper contains unsafe markup."))

    return ReportQualityAudit(
        artifact="bank_credit_report_html",
        issues=tuple(issues),
        metadata={
            "section_count": len(SECTION_SCHEMAS["bank_credit_paper"]),
            "url_count": _url_count(raw_html),
            "demo_mode": demo_mode,
        },
    )


def audit_bank_credit_report_pdf(pdf_path: Path, *, demo_mode: bool) -> ReportQualityAudit:
    """Extract and audit a Bank Credit Paper PDF artifact."""
    import pdfplumber

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return ReportQualityAudit(
            artifact="bank_credit_report_pdf",
            issues=(_issue("pdf_missing", f"PDF file does not exist: {pdf_path}"),),
            metadata={"page_count": 0, "demo_mode": demo_mode},
        )
    if not pdf_path.read_bytes().startswith(b"%PDF-"):
        return ReportQualityAudit(
            artifact="bank_credit_report_pdf",
            issues=(_issue("pdf_invalid_header", f"File does not look like a PDF: {pdf_path}"),),
            metadata={"page_count": 0, "demo_mode": demo_mode},
        )

    with pdfplumber.open(pdf_path) as pdf:
        page_texts = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(page_texts)
        page_count = len(pdf.pages)
    cover_text = _pdf_cover_text(text)
    issues = _credit_artifact_text_issues(
        text,
        cover_text=cover_text,
        demo_mode=demo_mode,
        artifact_label="pdf",
    )
    if demo_mode:
        demo_label = "DEMO DATA - NOT FOR RELIANCE"
        missing_demo_label_pages = [
            index for index, page_text in enumerate(page_texts, start=1) if demo_label not in page_text
        ]
        if missing_demo_label_pages:
            issues.append(
                _issue(
                    "missing_demo_credit_label_pages",
                    "Demo credit PDF must repeat the not-for-reliance label on every page. "
                    f"Missing pages: {missing_demo_label_pages}",
                )
            )
    return ReportQualityAudit(
        artifact="bank_credit_report_pdf",
        issues=tuple(issues),
        metadata={
            "page_count": page_count,
            "url_count": _url_count(text),
            "demo_mode": demo_mode,
        },
    )
