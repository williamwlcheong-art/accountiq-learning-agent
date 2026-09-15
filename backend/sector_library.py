"""Versioned generic sector research used by AccountIQ report generation.

The library is intentionally deterministic and local. It supplies a sourced New
Zealand sector baseline in both OpenAI provider mode and no-key evidence mode,
without representing generic sector characteristics as facts about the subject
business.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from market_intelligence import (
    enrich_research_brief_with_market_intelligence,
    market_intelligence_prompt_payload,
)


SCHEMA_VERSION = "1.0"
DEFAULT_SECTOR_REPORT_DIR = Path(__file__).resolve().parent.parent / "sector_reports"
REPORT_TYPE_SECTION = {
    "valuation_advisory": "valuation_report",
    "bank_credit_paper": "credit_paper",
}
_GENERIC_MATCH_WORDS = {
    "and",
    "business",
    "company",
    "group",
    "limited",
    "new",
    "nz",
    "of",
    "services",
    "the",
    "zealand",
}


@dataclass(frozen=True)
class SectorReportMatch:
    """A deterministic sector and optional sub-sector match."""

    sector_id: str
    sector_name: str
    report_file: str
    report: dict
    confidence: str
    matched_alias: str
    subsector_id: str = ""
    subsector_name: str = ""

    def metadata(self) -> dict:
        return {
            "sector_id": self.sector_id,
            "sector_name": self.sector_name,
            "subsector_id": self.subsector_id or None,
            "subsector_name": self.subsector_name or None,
            "confidence": self.confidence,
            "matched_alias": self.matched_alias,
            "report_file": self.report_file,
            "as_of_date": self.report.get("as_of_date"),
            "next_review_date": self.report.get("next_review_date"),
        }


def sector_report_dir() -> Path:
    configured = os.environ.get("ACCOUNTIQ_SECTOR_REPORT_DIR", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_SECTOR_REPORT_DIR


def _normalise(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalise(value).split()
        if len(token) >= 3 and token not in _GENERIC_MATCH_WORDS
    }


def _phrase_score(query: str, alias: str) -> int:
    normalised_alias = _normalise(alias)
    if not normalised_alias:
        return 0
    if query == normalised_alias:
        return 120 + len(normalised_alias.split())
    if re.search(rf"(?:^| ){re.escape(normalised_alias)}(?: |$)", query):
        return 80 + (4 * len(normalised_alias.split()))
    alias_tokens = _meaningful_tokens(normalised_alias)
    query_tokens = _meaningful_tokens(query)
    if len(alias_tokens) >= 2 and alias_tokens.issubset(query_tokens):
        return 45 + (3 * len(alias_tokens))
    return 0


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Sector library file must contain a JSON object: {path}")
    return value


def _validate_report(report: dict, path: Path) -> None:
    required = {
        "schema_version",
        "sector_id",
        "sector_name",
        "geography",
        "as_of_date",
        "next_review_date",
        "overview",
        "subsectors",
        "credit_analysis",
        "valuation_analysis",
        "market_research_sections",
        "sources",
        "limitations",
    }
    missing = sorted(required.difference(report))
    if missing:
        raise ValueError(f"Sector report {path.name} is missing: {', '.join(missing)}")
    if report["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported sector report schema {report['schema_version']} in {path.name}; "
            f"expected {SCHEMA_VERSION}"
        )
    if len(report.get("subsectors") or []) < 3:
        raise ValueError(f"Sector report {path.name} must contain at least three sub-sectors")
    if len(report.get("sources") or []) < 3:
        raise ValueError(f"Sector report {path.name} must contain at least three sources")
    market_sections = report.get("market_research_sections") or {}
    for section in REPORT_TYPE_SECTION.values():
        if len(str(market_sections.get(section) or "")) < 300:
            raise ValueError(f"Sector report {path.name} has an incomplete {section} narrative")


@lru_cache(maxsize=4)
def _load_library_cached(directory_value: str) -> tuple[dict, dict[str, dict]]:
    directory = Path(directory_value)
    index = _read_json(directory / "index.json")
    if index.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported sector index schema {index.get('schema_version')}; expected {SCHEMA_VERSION}"
        )
    reports: dict[str, dict] = {}
    seen_files: set[str] = set()
    for item in index.get("sectors") or []:
        sector_id = str(item.get("sector_id") or "")
        filename = Path(str(item.get("file") or "")).name
        if not sector_id or not filename or filename in seen_files:
            raise ValueError("Sector index contains a missing or duplicate sector/file entry")
        report_path = directory / filename
        report = _read_json(report_path)
        _validate_report(report, report_path)
        if report.get("sector_id") != sector_id:
            raise ValueError(f"Sector ID mismatch between index and {filename}")
        reports[sector_id] = report
        seen_files.add(filename)
    if len(reports) != len(index.get("sectors") or []):
        raise ValueError("Sector index contains duplicate sector IDs")
    return index, reports


def load_sector_library() -> tuple[dict, dict[str, dict]]:
    """Load and validate the current sector index and all registered packs."""
    return _load_library_cached(str(sector_report_dir().resolve()))


def clear_sector_library_cache() -> None:
    """Clear cached files for tests and controlled runtime refreshes."""
    _load_library_cached.cache_clear()


def match_sector_report(
    industry_sector: object,
    business_description: object = "",
) -> SectorReportMatch | None:
    """Match a sector and optional sub-sector using specific, versioned aliases."""
    index, reports = load_sector_library()
    sector_query = _normalise(industry_sector)
    combined_query = _normalise(f"{industry_sector or ''} {business_description or ''}")
    if not combined_query:
        return None

    best: tuple[int, dict, str] | None = None
    for item in index.get("sectors") or []:
        aliases = [item.get("sector_name"), *(item.get("aliases") or [])]
        for alias in aliases:
            sector_weight = _phrase_score(sector_query, str(alias)) + 30 if sector_query else 0
            score = max(sector_weight, _phrase_score(combined_query, str(alias)))
            if score and (best is None or score > best[0]):
                best = (score, item, str(alias))
    if best is None or best[0] < 48:
        return None

    _score, item, matched_alias = best
    report = reports[str(item["sector_id"])]
    best_subsector: tuple[int, dict] | None = None
    for subsector in report.get("subsectors") or []:
        aliases = [subsector.get("name"), *(subsector.get("aliases") or [])]
        subsector_score = max((_phrase_score(combined_query, str(alias)) for alias in aliases), default=0)
        if subsector_score and (best_subsector is None or subsector_score > best_subsector[0]):
            best_subsector = (subsector_score, subsector)

    confidence = "high" if best[0] >= 84 else "moderate"
    selected_subsector = best_subsector[1] if best_subsector and best_subsector[0] >= 48 else {}
    return SectorReportMatch(
        sector_id=str(item["sector_id"]),
        sector_name=str(item["sector_name"]),
        report_file=str(item["file"]),
        report=report,
        confidence=confidence,
        matched_alias=matched_alias,
        subsector_id=str(selected_subsector.get("id") or ""),
        subsector_name=str(selected_subsector.get("name") or ""),
    )


def _selected_subsector(match: SectorReportMatch) -> dict:
    if not match.subsector_id:
        return {}
    return next(
        (
            item
            for item in match.report.get("subsectors") or []
            if item.get("id") == match.subsector_id
        ),
        {},
    )


def sector_prompt_context(
    match: SectorReportMatch | None,
    report_type: str,
) -> str:
    """Return bounded, source-aware context suitable for an OpenAI prompt."""
    current_market = market_intelligence_prompt_payload(match, report_type)
    if match is None:
        return json.dumps(
            {"quarterly_market_intelligence": current_market},
            ensure_ascii=False,
            indent=2,
        )
    report = match.report
    section_name = REPORT_TYPE_SECTION.get(report_type, "credit_paper")
    analysis_key = "valuation_analysis" if section_name == "valuation_report" else "credit_analysis"
    sources = [
        {
            "title": source.get("title"),
            "publisher": source.get("publisher"),
            "url": source.get("url"),
            "published_date": source.get("published_date"),
            "supports": source.get("supports"),
        }
        for source in (report.get("sources") or [])[:6]
    ]
    payload = {
        "usage_boundary": (
            "Generic New Zealand sector baseline only. Test these characteristics against the "
            "subject business. Do not use this pack as proof of borrower facts, current market "
            "multiples, a company-specific beta, asset value, funding cost or credit approval."
        ),
        "match": match.metadata(),
        "overview": report.get("overview"),
        "selected_subsector": _selected_subsector(match) or None,
        "report_analysis": report.get(analysis_key),
        "draft_market_context": (report.get("market_research_sections") or {}).get(section_name),
        "sources": sources,
        "limitations": report.get("limitations"),
        "quarterly_market_intelligence": current_market,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def enrich_research_brief(
    brief: dict,
    match: SectorReportMatch | None,
    report_type: str,
) -> dict:
    """Merge a matched sector baseline into retained report research evidence."""
    result = copy.deepcopy(brief)
    if match is None:
        result["sector_library"] = {
            "matched": False,
            "reason": "No sufficiently specific sector alias matched the company sector or description.",
        }
        return enrich_research_brief_with_market_intelligence(
            result,
            match,
            report_type,
        )

    report = match.report
    section_name = REPORT_TYPE_SECTION.get(report_type, "credit_paper")
    market_narrative = str(
        (report.get("market_research_sections") or {}).get(section_name) or ""
    ).strip()
    existing_summary = str(result.get("sector_summary") or "").strip()
    pack_heading = (
        f"AccountIQ generic sector baseline ({match.sector_name}"
        f"{f' — {match.subsector_name}' if match.subsector_name else ''}; "
        f"reviewed {report.get('as_of_date')}): "
    )
    result["sector_summary"] = "\n\n".join(
        part for part in (existing_summary, pack_heading + market_narrative) if part
    )
    result["sector_library"] = {
        "matched": True,
        **match.metadata(),
        "usage_boundary": (
            "Generic sector context only; it is not evidence that the subject company has "
            "the stated characteristics. Current numerical market assumptions require "
            "separate, current evidence."
        ),
        "selected_subsector": _selected_subsector(match) or None,
        "credit_analysis": report.get("credit_analysis"),
        "valuation_analysis": report.get("valuation_analysis"),
        "sources": report.get("sources"),
        "limitations": report.get("limitations"),
    }

    sources = [str(value) for value in (result.get("sources") or []) if str(value).strip()]
    evidence_sources = list(result.get("evidence_sources") or [])
    accessed_at = f"{report.get('as_of_date')}T00:00:00+00:00"
    for source in report.get("sources") or []:
        url = str(source.get("url") or "").strip()
        if url and url not in sources:
            sources.append(url)
        if url and not any(str(item.get("url") or "") == url for item in evidence_sources if isinstance(item, dict)):
            supports = "; ".join(str(value) for value in source.get("supports") or [])
            evidence_sources.append(
                {
                    "url": url,
                    "title": str(source.get("title") or "Curated sector source"),
                    "source_type": "curated sector library",
                    "retrieved_at": accessed_at,
                    "excerpt": (
                        f"Curated source for generic {match.sector_name} context. "
                        f"Supports: {supports or 'sector structure and risk context'}."
                    ),
                    "status": "curated",
                    "error": "",
                }
            )
    result["sources"] = sources
    result["evidence_sources"] = evidence_sources

    limitations = [str(value) for value in (result.get("limitations") or [])]
    for limitation in report.get("limitations") or []:
        value = str(limitation)
        if value not in limitations:
            limitations.append(value)
    result["limitations"] = limitations
    return enrich_research_brief_with_market_intelligence(
        result,
        match,
        report_type,
    )


def sector_report_files() -> Iterable[Path]:
    """Yield every JSON pack registered by the current index."""
    index, _reports = load_sector_library()
    directory = sector_report_dir()
    for item in index.get("sectors") or []:
        yield directory / str(item["file"])
