"""Validation and matching tests for the AccountIQ sector research library."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse


BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sector_library import (  # noqa: E402
    enrich_research_brief,
    load_sector_library,
    match_sector_report,
    sector_prompt_context,
    sector_report_files,
)
from report_prompts import build_prompt  # noqa: E402


EXPECTED_SECTORS = {
    "logistics",
    "construction",
    "retail",
    "hospitality",
    "manufacturing",
    "professional_services",
    "early_childhood_education_and_care",
    "import_distribution",
}


def test_library_contains_all_initial_sector_reports():
    index, reports = load_sector_library()

    assert set(reports) == EXPECTED_SECTORS
    assert len(index["sectors"]) == 8
    assert {path.name for path in sector_report_files()} == {
        item["file"] for item in index["sectors"]
    }


def test_every_sector_pack_has_report_ready_depth_and_valid_sources():
    _index, reports = load_sector_library()

    for sector_id, report in reports.items():
        assert report["sector_id"] == sector_id
        assert report["geography"] == "New Zealand"
        assert len(report["overview"]["business_models"]) >= 4
        assert len(report["overview"]["demand_drivers"]) >= 4
        assert len(report["subsectors"]) >= 3
        assert len(report["credit_analysis"]["primary_risks"]) >= 4
        assert len(report["credit_analysis"]["monitoring_kpis"]) >= 5
        assert len(report["credit_analysis"]["diligence_questions"]) >= 4
        assert len(report["valuation_analysis"]["value_drivers"]) >= 4
        assert len(report["valuation_analysis"]["normalisation_focus"]) >= 4
        assert len(report["valuation_analysis"]["peer_selection"]) >= 3
        assert len(report["market_research_sections"]["credit_paper"]) >= 900
        assert len(report["market_research_sections"]["valuation_report"]) >= 900
        assert len(report["sources"]) >= 3
        assert len(report["limitations"]) >= 3

        source_ids = [source["id"] for source in report["sources"]]
        assert len(source_ids) == len(set(source_ids))
        for source in report["sources"]:
            parsed = urlparse(source["url"])
            assert parsed.scheme == "https"
            assert parsed.netloc
            assert source["publisher"]
            assert source["supports"]


def test_sector_pack_json_files_are_machine_readable():
    for path in sector_report_files():
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "1.0"
        assert payload["sector_id"]


def test_specific_sector_and_subsector_examples_match_deterministically():
    examples = {
        "towing and recovery": ("logistics", "towing_recovery"),
        "commercial main contractor": ("construction", "commercial_main_contracting"),
        "online retailer": ("retail", "ecommerce"),
        "cafe and restaurant": ("hospitality", "restaurants_cafes"),
        "metal fabrication": ("manufacturing", "metal_engineering"),
        "accounting firm": ("professional_services", "accounting_legal"),
        "ECE centre": (
            "early_childhood_education_and_care",
            "centre_based_private",
        ),
        "food importer": ("import_distribution", "food_beverage_import"),
    }

    for description, expected in examples.items():
        match = match_sector_report(description)
        assert match is not None
        assert (match.sector_id, match.subsector_id) == expected
        assert match.confidence == "high"


def test_business_description_can_refine_a_broad_sector_to_a_subsector():
    match = match_sector_report(
        "Logistics",
        "The company operates a secure yard and a specialised tow-truck fleet for insurers.",
    )

    assert match is not None
    assert match.sector_id == "logistics"
    assert match.subsector_id == "towing_recovery"


def test_generic_or_unknown_text_does_not_force_a_sector_match():
    assert match_sector_report("General SME", "A locally owned business.") is None
    assert match_sector_report("", "") is None


def test_report_type_context_is_bounded_and_keeps_evidence_boundary():
    match = match_sector_report("construction", "commercial builder")
    assert match is not None

    credit_context = sector_prompt_context(match, "bank_credit_paper")
    valuation_context = sector_prompt_context(match, "valuation_advisory")

    assert len(credit_context) < 25_000
    assert len(valuation_context) < 25_000
    assert "Generic New Zealand sector baseline only" in credit_context
    assert "current market multiples" in valuation_context
    assert "commercial_main_contracting" in credit_context
    assert "National Construction Pipeline Report" in valuation_context


def test_enrichment_records_pack_match_sources_and_generic_limitations():
    match = match_sector_report("early childhood education", "childcare centre")
    assert match is not None
    original = {
        "company_summary": "Company-specific source summary.",
        "sector_summary": "Independent research summary.",
        "sources": ["https://example.co.nz/company"],
        "evidence_sources": [],
        "limitations": ["Company website was not independently verified."],
    }

    enriched = enrich_research_brief(original, match, "bank_credit_paper")

    assert enriched is not original
    assert enriched["sector_library"]["matched"] is True
    assert enriched["sector_library"]["sector_id"] == "early_childhood_education_and_care"
    assert "AccountIQ generic sector baseline" in enriched["sector_summary"]
    assert "Independent research summary." in enriched["sector_summary"]
    assert "https://www.educationcounts.govt.nz/statistics/participation" in enriched["sources"]
    assert any(
        item["status"] == "curated"
        and item["source_type"] == "curated sector library"
        for item in enriched["evidence_sources"]
    )
    assert any("subject service" in item for item in enriched["limitations"])


def test_unmatched_enrichment_is_explicit_and_does_not_invent_sector_content():
    brief = {"sector_summary": "Existing independent sector text.", "sources": []}

    enriched = enrich_research_brief(brief, None, "valuation_advisory")

    assert enriched["sector_summary"] == "Existing independent sector text."
    assert enriched["sector_library"]["matched"] is False


def test_enriched_sector_brief_reaches_the_bank_credit_writing_prompt():
    match = match_sector_report(
        "Import distribution",
        "The borrower imports industrial parts and distributes them to trade customers.",
    )
    assert match is not None
    brief = enrich_research_brief(
        {
            "company_summary": "Borrower-specific public-source summary.",
            "sector_summary": "Independent borrower research.",
            "sources": [],
        },
        match,
        "bank_credit_paper",
    )

    _system_prompt, user_message = build_prompt(
        report_type="bank_credit_paper",
        company_name="Import Example Limited",
        industry="Import distribution",
        description="Industrial parts importer and distributor.",
        financial_rows=[],
        intake_answers={},
        management_team=[],
        ebitda_adjustments=[],
        bank_credit_figures={
            "annual_principal": 0,
            "dscr_table": [],
            "trend_table": [],
            "sensitivity": {},
        },
        credit_research_brief=brief,
    )

    assert "AccountIQ generic sector baseline" in user_message
    assert '"sector_id": "import_distribution"' in user_message
    assert "Foreign exchange, freight and supplier-price changes" in user_message
    assert "New Zealand Customs Service" in user_message
    assert "do not prove the borrower's demand or stock quality" in user_message
