"""Tests for the no-provider public-source evidence collector."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import evidence_research
from evidence_research import EvidenceSource, collect_evidence_research_sync, evidence_sources_table


def test_evidence_research_collects_only_approved_company_sources(monkeypatch):
    requested: list[tuple[str, str]] = []

    def fake_fetch(url: str, source_type: str):
        requested.append((url, source_type))
        if url.endswith("/about"):
            return (
                EvidenceSource(
                    url=url,
                    title="Example Towing - About",
                    source_type=source_type,
                    retrieved_at="2026-07-17T00:00:00+00:00",
                    excerpt="Example Towing provides roadside assistance, vehicle recovery and fleet support across Auckland.",
                ),
                [],
            )
        return (
            EvidenceSource(
                url=url,
                title="Example Towing",
                source_type=source_type,
                retrieved_at="2026-07-17T00:00:00+00:00",
                excerpt="Example Towing offers 24-hour towing, roadside assistance and commercial fleet support.",
            ),
            ["/about", "https://unrelated.example.com/about"],
        )

    monkeypatch.setattr(evidence_research, "_fetch_source", fake_fetch)
    monkeypatch.setattr(evidence_research, "_is_public_host", lambda _host: True)

    brief = collect_evidence_research_sync(
        company_name="Example Towing Limited",
        company_location="Auckland",
        industry_sector="Towing and recovery",
        company_website="https://example.co.nz",
        public_source_urls=["https://companies-register.example.org/example-towing"],
    )

    assert requested == [
        ("https://example.co.nz", "company website"),
        ("https://companies-register.example.org/example-towing", "management-supplied public source"),
        ("https://example.co.nz/about", "company website page"),
    ]
    assert len(brief.evidence_sources) == 3
    assert "24-hour towing" in brief.company_summary
    assert "open-web discovery" in brief.sector_summary
    assert brief.sources == [
        "https://example.co.nz",
        "https://companies-register.example.org/example-towing",
        "https://example.co.nz/about",
    ]


def test_evidence_research_rejects_private_network_sources():
    with pytest.raises(ValueError, match="public internet host"):
        collect_evidence_research_sync(
            company_name="Private Target",
            company_location="Auckland",
            industry_sector="Services",
            company_website="http://127.0.0.1/internal",
        )


def test_evidence_source_table_keeps_failed_source_out_of_factual_support():
    table = evidence_sources_table(
        [
            EvidenceSource(
                url="https://example.co.nz",
                title="Example",
                source_type="company website",
                retrieved_at="2026-07-17T00:00:00+00:00",
                excerpt="Example public business description.",
            ),
            EvidenceSource(
                url="https://unavailable.example.co.nz",
                title="Source not retrieved",
                source_type="management-supplied public source",
                retrieved_at="2026-07-17T00:00:00+00:00",
                excerpt="",
                status="not_retrieved",
                error="503 service unavailable",
            ),
        ]
    )

    assert "Reviewed public excerpt" in table["rows"][0][2]
    assert "not retrieved" in table["rows"][1][2]
    assert "not used for a factual claim" in table["rows"][1][2]
