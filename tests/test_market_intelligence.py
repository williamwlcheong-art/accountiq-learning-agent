import sys
from datetime import date
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import _e2e_report_content, _render_report_sections_html
import market_intelligence as market_intelligence_module
from market_intelligence import (
    MarketIntelligenceStaleError,
    apply_market_intelligence_to_report_content,
    enrich_research_brief_with_market_intelligence,
    load_current_market_intelligence,
    market_intelligence_prompt_payload,
)
from report_prompts import SECTION_SCHEMAS
from report_rendering import render_report_html
from report_validation import validate_generated_report
from sector_library import load_sector_library, match_sector_report


def test_current_quarterly_snapshot_has_macro_sources_and_every_sector():
    _index, snapshot = load_current_market_intelligence()
    sector_index, _reports = load_sector_library()

    assert snapshot["snapshot_id"] == "nz-market-intelligence-2026-q3-2026-07-27"
    assert snapshot["as_of_date"] == "2026-07-27"
    assert len(snapshot["macro_indicators"]) >= 6
    assert {"cpi", "ocr", "gdp_qoq", "net_migration", "population", "unemployment"} <= {
        item["id"] for item in snapshot["macro_indicators"]
    }
    assert {item["sector_id"] for item in sector_index["sectors"]} == set(snapshot["sector_scale"])
    assert len(snapshot["sources"]) >= 8
    assert all(
        len(series["values"]) >= 8
        for chart in snapshot["charts"]
        for series in chart["series"]
    )


def test_current_snapshot_fails_closed_after_review_date(monkeypatch):
    monkeypatch.setattr(
        market_intelligence_module,
        "_new_zealand_today",
        lambda: date(2026, 10, 27),
    )

    with pytest.raises(MarketIntelligenceStaleError, match="2026-10-26"):
        load_current_market_intelligence()


def test_private_sector_scale_is_not_described_as_market_capitalisation():
    _index, snapshot = load_current_market_intelligence()
    for sector_id, measure in snapshot["sector_scale"].items():
        if measure["measure_kind"] != "sector_turnover_proxy":
            continue
        assert measure["rolling_four_quarter_nzd_m"] > 0, sector_id
        assert measure["series_reference"].startswith("BDCQ."), sector_id
        assert "market cap" not in str(measure).lower(), sector_id
        assert len(measure["series"]) == 8, sector_id


def test_ece_uses_structural_scale_and_labels_broad_comparator_low_fit():
    _index, snapshot = load_current_market_intelligence()
    ece = snapshot["sector_scale"]["early_childhood_education_and_care"]

    assert ece["measure_kind"] == "structural_scale"
    assert {item["label"] for item in ece["metrics"]} >= {
        "Licensed services",
        "Children enrolled",
        "Teaching staff",
    }
    assert ece["broad_comparator"]["boundary_fit"] == "low"
    assert "Do not present" in ece["broad_comparator"]["note"]


def test_prompt_payload_and_research_brief_keep_periods_boundaries_and_sources():
    match = match_sector_report("Towing and recovery", "Vehicle towing and roadside recovery")
    assert match is not None

    payload = market_intelligence_prompt_payload(match, "bank_credit_paper")
    assert payload["matched_sector_scale"]["boundary_label"] == "Transport, Postal and Warehousing"
    assert payload["macro_indicators"][0]["period"] == "June 2026 quarter"
    assert "never market capitalisation" in payload["writing_instruction"]

    brief = enrich_research_brief_with_market_intelligence(
        {"sources": [], "limitations": []},
        match,
        "bank_credit_paper",
    )
    assert brief["market_intelligence"]["snapshot"]["next_review_date"] == "2026-10-26"
    assert any("rbnz.govt.nz" in url for url in brief["sources"])
    assert any(
        source["source_type"] == "official quarterly market intelligence"
        for source in brief["evidence_sources"]
    )


def test_market_content_adds_tables_and_chart_ready_series_to_both_reports():
    match = match_sector_report("Construction", "Commercial construction contractor")
    assert match is not None

    for report_type, section_key in (
        ("valuation_advisory", "market_position"),
        ("bank_credit_paper", "industry_and_competitive_landscape"),
    ):
        content = _e2e_report_content(report_type)
        enriched = apply_market_intelligence_to_report_content(content, match, report_type)
        section = enriched[section_key]

        assert section["table"]["headers"][0] == "Indicator"
        assert len(section["table"]["rows"]) == 6
        assert section["sector_scale_table"]["rows"][0][0] == "Four-quarter nominal sales proxy"
        assert any("stats.govt.nz" in row[-1] for row in section["market_sources_table"]["rows"])
        assert len(section["market_charts"]) == 4
        assert section["market_snapshot"]["snapshot_id"] == "nz-market-intelligence-2026-q3-2026-07-27"
        validate_generated_report(enriched, report_type)


def test_report_html_renders_market_graphs_legends_sources_and_tables():
    match = match_sector_report("Manufacturing", "New Zealand manufacturer")
    content = apply_market_intelligence_to_report_content(
        _e2e_report_content("valuation_advisory"),
        match,
        "valuation_advisory",
    )

    rendered = _render_report_sections_html(content, SECTION_SCHEMAS["valuation_advisory"])

    assert rendered.count('class="market-line-chart"') == 4
    assert "Annual CPI inflation and Official Cash Rate" in rendered
    assert "Manufacturing quarterly sales" in rendered
    assert "Source: Stats NZ, Reserve Bank of New Zealand" in rendered
    assert "Sector scale and boundary" in rendered
    assert "Market data sources" in rendered
    assert "https://www.stats.govt.nz/" in rendered


def test_report_pdf_html_renders_market_graphs_sources_and_sector_boundary():
    match = match_sector_report("Retail", "New Zealand multi-site retailer")
    content = apply_market_intelligence_to_report_content(
        _e2e_report_content("valuation_advisory"),
        match,
        "valuation_advisory",
    )
    market_section = {"market_position": content["market_position"]}
    html = render_report_html(
        company_name="Quarterly Market Example Limited",
        report_type="valuation_advisory",
        sections=market_section,
        section_order=["market_position"],
        generated_at="2026-07-27",
    )

    assert "Annual CPI inflation and Official Cash Rate" in html
    assert "Retail Trade quarterly sales" in html
    assert "Stats NZ Business Financial Data" in html
    assert "Sector scale and boundary" in html
    assert "Four-quarter nominal sales proxy" in html
    assert "Market data sources" in html
