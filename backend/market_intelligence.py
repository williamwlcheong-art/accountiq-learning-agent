"""Versioned quarterly New Zealand market intelligence for AccountIQ reports.

The numeric layer is deterministic and independent of the narrative provider.
This keeps the source period, unit, industry boundary and chart series intact
in provider, evidence and demo reports.
"""

from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from pathlib import Path


SCHEMA_VERSION = "1.0"
DEFAULT_MARKET_INTELLIGENCE_DIR = (
    Path(__file__).resolve().parent.parent / "sector_reports" / "quarterly"
)
MARKET_SECTION_BY_REPORT_TYPE = {
    "valuation_advisory": "market_position",
    "bank_credit_paper": "industry_and_competitive_landscape",
}


def market_intelligence_dir() -> Path:
    configured = os.environ.get("ACCOUNTIQ_MARKET_INTELLIGENCE_DIR", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_MARKET_INTELLIGENCE_DIR


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Market intelligence file must contain a JSON object: {path}")
    return value


def _validate_snapshot(snapshot: dict, path: Path) -> None:
    required = {
        "schema_version",
        "snapshot_id",
        "quarter",
        "geography",
        "as_of_date",
        "next_review_date",
        "usage_boundary",
        "economy_summary",
        "macro_indicators",
        "charts",
        "sector_scale",
        "sources",
    }
    missing = sorted(required.difference(snapshot))
    if missing:
        raise ValueError(
            f"Market intelligence snapshot {path.name} is missing: {', '.join(missing)}"
        )
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported market intelligence schema {snapshot.get('schema_version')} "
            f"in {path.name}; expected {SCHEMA_VERSION}"
        )
    source_ids = {
        str(source.get("id") or "")
        for source in snapshot.get("sources") or []
        if isinstance(source, dict)
    }
    if "" in source_ids or len(source_ids) < 6:
        raise ValueError(f"Market intelligence snapshot {path.name} has incomplete sources")
    for indicator in snapshot.get("macro_indicators") or []:
        if not isinstance(indicator, dict) or indicator.get("source_id") not in source_ids:
            raise ValueError(f"Market indicator in {path.name} has an invalid source")
    for chart in snapshot.get("charts") or []:
        if not isinstance(chart, dict) or not chart.get("title"):
            raise ValueError(f"Market chart in {path.name} is incomplete")
        for source_id in chart.get("source_ids") or []:
            if source_id not in source_ids:
                raise ValueError(f"Market chart in {path.name} has an invalid source")
        for series in chart.get("series") or []:
            values = series.get("values") if isinstance(series, dict) else None
            if not isinstance(values, list) or len(values) < 8:
                raise ValueError(
                    f"Market chart {chart.get('id')} in {path.name} needs at least eight points"
                )
    if not isinstance(snapshot.get("sector_scale"), dict) or not snapshot["sector_scale"]:
        raise ValueError(f"Market intelligence snapshot {path.name} has no sector measures")


@lru_cache(maxsize=4)
def _load_current_cached(directory_value: str) -> tuple[dict, dict]:
    directory = Path(directory_value)
    index = _read_json(directory / "index.json")
    if index.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported market intelligence index schema {index.get('schema_version')}; "
            f"expected {SCHEMA_VERSION}"
        )
    filename = Path(str(index.get("current_snapshot") or "")).name
    if not filename:
        raise ValueError("Market intelligence index has no current snapshot")
    snapshot_path = directory / filename
    snapshot = _read_json(snapshot_path)
    _validate_snapshot(snapshot, snapshot_path)
    indexed = next(
        (
            item
            for item in index.get("snapshots") or []
            if isinstance(item, dict) and Path(str(item.get("file") or "")).name == filename
        ),
        None,
    )
    if not indexed or indexed.get("snapshot_id") != snapshot.get("snapshot_id"):
        raise ValueError("Current market intelligence snapshot is not registered correctly")
    return index, snapshot


def load_current_market_intelligence() -> tuple[dict, dict]:
    """Load and validate the registered current quarterly snapshot."""
    return _load_current_cached(str(market_intelligence_dir().resolve()))


def clear_market_intelligence_cache() -> None:
    _load_current_cached.cache_clear()


def _sector_id(match: object | None) -> str:
    return str(getattr(match, "sector_id", "") or "")


def _source_map(snapshot: dict) -> dict[str, dict]:
    return {
        str(source.get("id")): source
        for source in snapshot.get("sources") or []
        if isinstance(source, dict) and source.get("id")
    }


def _format_value(value: object, unit: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "")
    if unit == "%":
        return f"{number:.1f}%"
    if unit == "% q/q":
        return f"{number:+.1f}% q/q"
    if unit in {"people", "services", "children"}:
        return f"{number:,.0f}"
    return f"{number:,.1f} {unit}".strip()


def market_intelligence_prompt_payload(
    match: object | None,
    report_type: str,
) -> dict:
    """Return bounded current-market context for report narrative generation."""
    _index, snapshot = load_current_market_intelligence()
    sector = copy.deepcopy((snapshot.get("sector_scale") or {}).get(_sector_id(match)))
    sources = [
        {
            "id": source.get("id"),
            "publisher": source.get("publisher"),
            "title": source.get("title"),
            "url": source.get("url"),
            "published_date": source.get("published_date"),
        }
        for source in snapshot.get("sources") or []
    ]
    implication_key = (
        "valuation_implications"
        if report_type == "valuation_advisory"
        else "credit_implications"
    )
    economy = snapshot.get("economy_summary") or {}
    return {
        "usage_boundary": snapshot.get("usage_boundary"),
        "snapshot": {
            "snapshot_id": snapshot.get("snapshot_id"),
            "quarter": snapshot.get("quarter"),
            "as_of_date": snapshot.get("as_of_date"),
            "next_review_date": snapshot.get("next_review_date"),
        },
        "economy": {
            "headline": economy.get("headline"),
            "narrative": economy.get("narrative"),
            "report_implications": economy.get(implication_key),
        },
        "macro_indicators": snapshot.get("macro_indicators"),
        "matched_sector_scale": sector,
        "sources": sources,
        "writing_instruction": (
            "Use the period and unit exactly as supplied. Describe monetary private-sector "
            "measures as turnover or scale proxies, never market capitalisation. Keep the "
            "industry boundary and limitations visible and do not infer subject-company "
            "market share or performance."
        ),
    }


def market_intelligence_prompt_context(
    match: object | None,
    report_type: str,
) -> str:
    return json.dumps(
        {"quarterly_market_intelligence": market_intelligence_prompt_payload(match, report_type)},
        ensure_ascii=False,
        indent=2,
    )


def enrich_research_brief_with_market_intelligence(
    brief: dict,
    match: object | None,
    report_type: str,
) -> dict:
    """Retain quarterly sources and report-ready evidence in a research brief."""
    result = copy.deepcopy(brief)
    payload = market_intelligence_prompt_payload(match, report_type)
    _index, snapshot = load_current_market_intelligence()
    result["market_intelligence"] = payload

    urls = [str(value) for value in (result.get("sources") or []) if str(value).strip()]
    evidence_sources = list(result.get("evidence_sources") or [])
    retrieved_at = f"{snapshot.get('as_of_date')}T00:00:00+12:00"
    for source in snapshot.get("sources") or []:
        url = str(source.get("url") or "").strip()
        if url and url not in urls:
            urls.append(url)
        if url and not any(
            isinstance(item, dict) and str(item.get("url") or "") == url
            for item in evidence_sources
        ):
            supports = "; ".join(str(value) for value in source.get("supports") or [])
            evidence_sources.append(
                {
                    "url": url,
                    "title": str(source.get("title") or "Quarterly market source"),
                    "source_type": "official quarterly market intelligence",
                    "retrieved_at": retrieved_at,
                    "excerpt": supports,
                    "status": "curated",
                    "error": "",
                }
            )
    result["sources"] = urls
    result["evidence_sources"] = evidence_sources

    limitations = [str(value) for value in (result.get("limitations") or [])]
    boundary = str(snapshot.get("usage_boundary") or "").strip()
    if boundary and boundary not in limitations:
        limitations.append(boundary)
    sector = payload.get("matched_sector_scale")
    sector_limitation = str((sector or {}).get("limitations") or "").strip()
    if sector_limitation and sector_limitation not in limitations:
        limitations.append(sector_limitation)
    result["limitations"] = limitations
    return result


def _macro_table(snapshot: dict) -> dict:
    return {
        "headers": ["Indicator", "Latest", "Reference period", "Report interpretation"],
        "rows": [
            [
                str(item.get("label") or ""),
                _format_value(item.get("value"), str(item.get("unit") or "")),
                str(item.get("period") or ""),
                str(item.get("commentary") or ""),
            ]
            for item in snapshot.get("macro_indicators") or []
            if isinstance(item, dict)
        ],
    }


def _sector_scale_table(sector: dict | None) -> dict:
    if not sector:
        return {
            "headers": ["Sector measure", "Latest evidence", "Boundary and interpretation"],
            "rows": [[
                "No matched sector measure",
                "Not available",
                "The New Zealand macro indicators still apply; no sufficiently specific sector proxy was selected.",
            ]],
        }
    if sector.get("measure_kind") == "structural_scale":
        rows = [
            [
                str(metric.get("label") or ""),
                _format_value(metric.get("value"), str(metric.get("unit") or "")),
                str(sector.get("latest_period") or ""),
            ]
            for metric in sector.get("metrics") or []
            if isinstance(metric, dict)
        ]
        rows.append([
            "Use boundary",
            "Structural counts only",
            str(sector.get("limitations") or ""),
        ])
        return {
            "headers": ["Sector measure", "Latest evidence", "Period / boundary"],
            "rows": rows,
        }
    rolling = float(sector.get("rolling_four_quarter_nzd_m") or 0)
    latest = float(sector.get("latest_quarter_nzd_m") or 0)
    change = float(sector.get("annual_change_pct") or 0)
    return {
        "headers": ["Sector measure", "Latest evidence", "Boundary and interpretation"],
        "rows": [
            [
                "Four-quarter nominal sales proxy",
                f"NZ${rolling / 1000:,.1f}bn ({change:+.1f}% vs prior four quarters)",
                str(sector.get("boundary_label") or ""),
            ],
            [
                "Latest seasonally adjusted quarter",
                f"NZ${latest / 1000:,.1f}bn",
                str(sector.get("latest_period") or ""),
            ],
            [
                "Source series",
                str(sector.get("series_reference") or ""),
                str(sector.get("limitations") or ""),
            ],
        ],
    }


def _sector_chart(sector: dict | None) -> dict | None:
    if not sector or sector.get("measure_kind") != "sector_turnover_proxy":
        return None
    series = sector.get("series")
    if not isinstance(series, list) or len(series) < 2:
        return None
    return {
        "id": "sector_sales",
        "title": f"{sector.get('boundary_label')} quarterly sales",
        "subtitle": "Seasonally adjusted current-price sales; shown as a broad sector turnover proxy.",
        "type": "line",
        "unit": "NZD millions",
        "source_ids": ["stats_nz_bfd"],
        "series": [{"name": "Quarterly sales", "values": copy.deepcopy(series)}],
        "note": str(sector.get("limitations") or ""),
    }


def _market_sources_table(snapshot: dict, sector: dict | None) -> dict:
    relevant_ids = {
        str(item.get("source_id") or "")
        for item in snapshot.get("macro_indicators") or []
        if isinstance(item, dict)
    }
    if sector:
        if sector.get("measure_kind") == "structural_scale":
            relevant_ids.update({"education_counts_ece", "stats_nz_bfd"})
        else:
            relevant_ids.add("stats_nz_bfd")
        secondary = sector.get("secondary_context")
        if isinstance(secondary, dict) and secondary.get("source_id"):
            relevant_ids.add(str(secondary["source_id"]))
    return {
        "headers": ["Publisher / source", "Published", "Used for", "URL"],
        "rows": [
            [
                f"{source.get('publisher')} — {source.get('title')}",
                str(source.get("published_date") or "Living source"),
                "; ".join(str(value) for value in source.get("supports") or []),
                str(source.get("url") or ""),
            ]
            for source in snapshot.get("sources") or []
            if isinstance(source, dict) and str(source.get("id") or "") in relevant_ids
        ],
    }


def apply_market_intelligence_to_report_content(
    content: dict,
    match: object | None,
    report_type: str,
) -> dict:
    """Add deterministic macro tables and chart payloads to a report market section."""
    result = copy.deepcopy(content)
    section_key = MARKET_SECTION_BY_REPORT_TYPE.get(report_type)
    if not section_key or section_key not in result:
        return result
    _index, snapshot = load_current_market_intelligence()
    sector = (snapshot.get("sector_scale") or {}).get(_sector_id(match))
    current = result.get(section_key)
    if isinstance(current, dict):
        provider_narrative = str(current.get("narrative") or "").strip()
    else:
        provider_narrative = str(current or "").strip()
    economy = snapshot.get("economy_summary") or {}
    implication = str(
        economy.get(
            "valuation_implications"
            if report_type == "valuation_advisory"
            else "credit_implications"
        )
        or ""
    ).strip()
    sector_commentary = " ".join(
        value
        for value in (
            str((sector or {}).get("interpretation") or "").strip(),
            str((sector or {}).get("limitations") or "").strip(),
        )
        if value
    )
    narrative_parts = [
        provider_narrative,
        (
            f"## New Zealand economic setting — {snapshot.get('quarter')}\n"
            f"{economy.get('narrative')} {implication}"
        ),
    ]
    if sector_commentary:
        narrative_parts.append(
            f"## Sector scale and boundary\n{sector_commentary}"
        )
    charts = copy.deepcopy(snapshot.get("charts") or [])
    sector_chart = _sector_chart(sector)
    if sector_chart:
        charts.append(sector_chart)
    result[section_key] = {
        "narrative": "\n\n".join(part for part in narrative_parts if part),
        "table": _macro_table(snapshot),
        "sector_scale_table": _sector_scale_table(sector),
        "market_sources_table": _market_sources_table(snapshot, sector),
        "market_charts": charts,
        "market_snapshot": {
            "snapshot_id": snapshot.get("snapshot_id"),
            "as_of_date": snapshot.get("as_of_date"),
            "next_review_date": snapshot.get("next_review_date"),
            "usage_boundary": snapshot.get("usage_boundary"),
        },
    }
    return result
