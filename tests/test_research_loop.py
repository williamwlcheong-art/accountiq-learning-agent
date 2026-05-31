"""Offline unit tests for backend/research_loop.py (Phase 05.1 REPT-01).

All tests in this file are OFFLINE — they exercise Pydantic validation
and the four guardrails in _apply_guardrails(brief) directly. No live
Anthropic API calls are made. Live API integration is exercised in the
Wave 2 wizard checkpoint (Plan 04) and offline-only in CI.
"""

import sys
import inspect
from pathlib import Path
import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research_loop import (
    ResearchBrief,
    WEB_SEARCH_TOOL,
    _apply_guardrails,
    _extract_json_from_response,
    run_valuation_research,
)


# ---------------------------------------------------------------------------
# Helper — valid baseline kwargs
# ---------------------------------------------------------------------------

def _valid_brief_kwargs() -> dict:
    return {
        "company_summary": "Propellerhead Limited is a NZ-based digital agency founded in 2014 with offices in Auckland. " * 2,
        "sector_summary": "The NZ digital agency sector is mature with notable players including Assembly, DNA, and Resn. " * 2,
        "comparable_transactions": "Recent NZ digital agency M&A: example deal A at 6x EBITDA.",
        "ev_ebitda_low": 3.5,
        "ev_ebitda_high": 6.0,
        "risk_free_rate": 4.65,
        "erp": 5.94,
        "industry_beta": 1.08,
        "industry_category": "Software (System & Application)",
        "inflation_rate": 2.5,
        "sources": [
            "https://rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
            "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/totalbeta.html",
        ],
    }


# ---------------------------------------------------------------------------
# Duck-typed stubs for _extract_json_from_response (no anthropic import needed)
# ---------------------------------------------------------------------------

class _StubTextBlock:
    type = "text"
    def __init__(self, text): self.text = text


class _StubResponse:
    def __init__(self, content): self.content = content


# ---------------------------------------------------------------------------
# Pydantic field validation tests
# ---------------------------------------------------------------------------

def test_research_brief_accepts_valid_inputs():
    """A brief with realistic NZ inputs should construct without exception."""
    brief = ResearchBrief(**_valid_brief_kwargs())
    assert brief.risk_free_rate == 4.65
    assert brief.erp == 5.94
    assert brief.industry_beta == 1.08


def test_research_brief_rejects_negative_risk_free_rate():
    """Pydantic Field(gt=0) must reject negative risk_free_rate."""
    kwargs = _valid_brief_kwargs()
    kwargs["risk_free_rate"] = -1.0
    with pytest.raises(ValidationError):
        ResearchBrief(**kwargs)


def test_research_brief_rejects_oversized_beta():
    """Pydantic Field(lt=10) must reject industry_beta=15.0."""
    kwargs = _valid_brief_kwargs()
    kwargs["industry_beta"] = 15.0
    with pytest.raises(ValidationError):
        ResearchBrief(**kwargs)


def test_research_brief_rejects_short_company_summary():
    """Pydantic Field(min_length=50) must reject company_summary of 10 chars."""
    kwargs = _valid_brief_kwargs()
    kwargs["company_summary"] = "too short"
    with pytest.raises(ValidationError):
        ResearchBrief(**kwargs)


def test_research_brief_rejects_empty_sources():
    """Pydantic Field(min_length=1) must reject an empty sources list."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = []
    with pytest.raises(ValidationError):
        ResearchBrief(**kwargs)


# ---------------------------------------------------------------------------
# Guardrail tests — decimal-form WACC
# ---------------------------------------------------------------------------

def test_guardrail_decimal_form_risk_free_rate():
    """risk_free_rate=0.0465 passes Pydantic (>0) but fails decimal-form guardrail."""
    kwargs = _valid_brief_kwargs()
    kwargs["risk_free_rate"] = 0.0465
    brief = ResearchBrief(**kwargs)   # Pydantic accepts (0.0465 > 0)
    with pytest.raises(ValueError, match="decimal form"):
        _apply_guardrails(brief)


def test_guardrail_decimal_form_erp():
    """erp=0.0594 passes Pydantic but fails decimal-form guardrail."""
    kwargs = _valid_brief_kwargs()
    kwargs["erp"] = 0.0594
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="decimal form"):
        _apply_guardrails(brief)


# ---------------------------------------------------------------------------
# Guardrail tests — placeholder detection
# ---------------------------------------------------------------------------

def test_guardrail_placeholder_in_company_summary():
    """company_summary containing 'TBC' (as a word boundary) raises ValueError."""
    kwargs = _valid_brief_kwargs()
    kwargs["company_summary"] = "Company analysis TBC because data not yet available for this entity in the NZ market."
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="placeholder"):
        _apply_guardrails(brief)


def test_guardrail_placeholder_in_sector_summary():
    """sector_summary containing 'N/A' raises ValueError."""
    kwargs = _valid_brief_kwargs()
    kwargs["sector_summary"] = (
        "Sector data N/A for this quarter. Further research required in the NZ digital services space. " * 2
    )
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="placeholder"):
        _apply_guardrails(brief)


def test_guardrail_placeholder_in_industry_category():
    """industry_category containing 'to be confirmed' raises ValueError."""
    kwargs = _valid_brief_kwargs()
    kwargs["industry_category"] = "to be confirmed"
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="placeholder"):
        _apply_guardrails(brief)


# ---------------------------------------------------------------------------
# Guardrail tests — missing RBNZ/Damodaran sources
# ---------------------------------------------------------------------------

def test_guardrail_missing_rbnz_and_damodaran_sources():
    """Sources with no rbnz.govt.nz or damodaran URL raise ValueError."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = [
        "https://www.someblog.com/wacc",
        "https://example.com",
    ]
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="RBNZ or Damodaran"):
        _apply_guardrails(brief)


def test_guardrail_rbnz_source_accepted():
    """A source containing 'rbnz.govt.nz' should pass the source guardrail."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = ["https://rbnz.govt.nz/statistics"]
    brief = ResearchBrief(**kwargs)
    # Should not raise ValueError for the source guardrail
    # (may raise for WACC range — use valid values)
    _apply_guardrails(brief)  # no exception expected


def test_guardrail_damodaran_source_accepted():
    """A source containing 'damodaran' substring should pass the source guardrail."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = ["https://pages.stern.nyu.edu/~adamodar/datafile/totalbeta.html"]
    brief = ResearchBrief(**kwargs)
    _apply_guardrails(brief)  # no exception expected


# ---------------------------------------------------------------------------
# Guardrail tests — WACC range check
# ---------------------------------------------------------------------------

def test_guardrail_wacc_too_low():
    """mid WACC = 2.0 + 0.6*3.0 = 3.8 < 8.0 → ValueError."""
    kwargs = _valid_brief_kwargs()
    kwargs["risk_free_rate"] = 2.0
    kwargs["industry_beta"] = 0.6
    kwargs["erp"] = 3.0
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="8-20"):
        _apply_guardrails(brief)


def test_guardrail_wacc_too_high():
    """mid WACC = 8.0 + 2.5*8.0 = 28.0 > 20.0 → ValueError."""
    kwargs = _valid_brief_kwargs()
    kwargs["risk_free_rate"] = 8.0
    kwargs["industry_beta"] = 2.5
    kwargs["erp"] = 8.0
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="8-20"):
        _apply_guardrails(brief)


def test_guardrail_wacc_in_range_accepted():
    """mid WACC = 4.65 + 1.08*5.94 = 11.07 — passes WACC range guardrail."""
    kwargs = _valid_brief_kwargs()  # 4.65, 1.08, 5.94 → mid ≈ 11.07
    brief = ResearchBrief(**kwargs)
    _apply_guardrails(brief)  # no exception expected


# ---------------------------------------------------------------------------
# JSON extraction tests
# ---------------------------------------------------------------------------

def test_extract_json_from_response_strips_code_fences():
    """_extract_json_from_response must strip ```json ... ``` fences and parse dict."""
    raw = '```json\n{"company_summary": "x", "risk_free_rate": 4.65}\n```'
    response = _StubResponse([_StubTextBlock(raw)])
    data = _extract_json_from_response(response)
    assert data["risk_free_rate"] == 4.65


def test_extract_json_from_response_raises_when_no_text_block():
    """Empty content list must raise ValueError."""
    response = _StubResponse([])
    with pytest.raises(ValueError):
        _extract_json_from_response(response)


# ---------------------------------------------------------------------------
# Async shape and module config tests
# ---------------------------------------------------------------------------

def test_run_valuation_research_is_async():
    """run_valuation_research must be a coroutine function (async def)."""
    assert inspect.iscoroutinefunction(run_valuation_research)


def test_module_exports_web_search_tool_config():
    """WEB_SEARCH_TOOL must match the AI-SPEC shape exactly."""
    assert WEB_SEARCH_TOOL["type"] == "web_search_20250305"
    assert WEB_SEARCH_TOOL["name"] == "web_search"
    assert WEB_SEARCH_TOOL["max_uses"] == 15
    assert WEB_SEARCH_TOOL["user_location"]["country"] == "NZ"
    assert WEB_SEARCH_TOOL["user_location"]["timezone"] == "Pacific/Auckland"
