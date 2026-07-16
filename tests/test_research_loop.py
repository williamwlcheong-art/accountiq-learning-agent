"""Offline unit tests for backend/research_loop.py (Phase 05.1 REPT-01).

All tests in this file are OFFLINE — they exercise Pydantic validation
and the four guardrails in _apply_guardrails(brief) directly. No live
Anthropic API calls are made. Live API integration is exercised in the
Wave 2 wizard checkpoint (Plan 04) and offline-only in CI.
"""

import sys
import inspect
from types import SimpleNamespace
from pathlib import Path
import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research_loop import (
    RESEARCH_SYSTEM_PROMPT,
    ResearchBrief,
    WEB_SEARCH_TOOL,
    _apply_guardrails,
    _extract_json_from_response,
    run_valuation_research,
)
import research_loop as research_loop_module


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
# Guardrail tests — missing RBNZ or Damodaran sources
# ---------------------------------------------------------------------------

def test_guardrail_missing_rbnz_and_damodaran_sources():
    """Sources with neither rbnz.govt.nz nor Damodaran URL raise ValueError."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = [
        "https://www.someblog.com/wacc",
        "https://example.com",
    ]
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="both RBNZ and Damodaran"):
        _apply_guardrails(brief)


def test_guardrail_rejects_rbnz_without_damodaran_source():
    """RBNZ alone cannot verify Damodaran ERP/beta inputs."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = ["https://rbnz.govt.nz/statistics"]
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="Damodaran"):
        _apply_guardrails(brief)


def test_guardrail_rejects_damodaran_without_rbnz_source():
    """Damodaran alone cannot verify NZ risk-free-rate or inflation inputs."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = ["https://pages.stern.nyu.edu/~adamodar/datafile/totalbeta.html"]
    brief = ResearchBrief(**kwargs)
    with pytest.raises(ValueError, match="RBNZ"):
        _apply_guardrails(brief)


def test_guardrail_rbnz_and_damodaran_sources_accepted():
    """Research needs both source families for a professional WACC evidence trail."""
    kwargs = _valid_brief_kwargs()
    brief = ResearchBrief(**kwargs)
    _apply_guardrails(brief)  # no exception expected


def test_guardrail_rejects_source_without_http_scheme():
    """Research sources must be real URLs so report source tables can render them."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = [
        "rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
        "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/totalbeta.html",
    ]
    brief = ResearchBrief(**kwargs)

    with pytest.raises(ValueError, match="valid http"):
        _apply_guardrails(brief)


def test_guardrail_rejects_source_with_unsupported_scheme():
    """Only http(s) sources should be accepted as valuation report evidence."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = [
        "ftp://rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
        "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/totalbeta.html",
    ]
    brief = ResearchBrief(**kwargs)

    with pytest.raises(ValueError, match="valid http"):
        _apply_guardrails(brief)


def test_guardrail_rejects_lookalike_rbnz_source_host():
    """A lookalike host containing rbnz.govt.nz must not pass as official RBNZ evidence."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = [
        "https://rbnz.govt.nz.evil.example/statistics",
        "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/totalbeta.html",
    ]
    brief = ResearchBrief(**kwargs)

    with pytest.raises(ValueError, match="RBNZ"):
        _apply_guardrails(brief)


def test_guardrail_rejects_lookalike_damodaran_source_host():
    """A URL merely mentioning Damodaran must not pass as official Damodaran evidence."""
    kwargs = _valid_brief_kwargs()
    kwargs["sources"] = [
        "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
        "https://example.com/damodaran-total-beta",
    ]
    brief = ResearchBrief(**kwargs)

    with pytest.raises(ValueError, match="Damodaran"):
        _apply_guardrails(brief)


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


def test_research_prompt_requires_full_http_source_urls():
    """The prompt should ask for renderable URLs, matching the source guardrail."""
    assert '"sources": ["https://...", "https://...", ...]' in RESEARCH_SYSTEM_PROMPT
    assert "full http:// or https:// URL" in RESEARCH_SYSTEM_PROMPT
    assert "no bare domains or host-only strings" in RESEARCH_SYSTEM_PROMPT


def test_research_loop_uses_credentials_saved_after_module_import(monkeypatch):
    """Admin Settings updates os.environ at runtime; research must see the new values."""
    captured = {}
    valid_json = __import__("json").dumps(_valid_brief_kwargs())

    class _FakeMessages:
        def create(self, **kwargs):
            captured["model"] = kwargs["model"]
            return SimpleNamespace(
                content=[_StubTextBlock(valid_json)],
                stop_reason="end_turn",
                usage=SimpleNamespace(
                    server_tool_use={},
                    input_tokens=100,
                    output_tokens=200,
                ),
            )

    class _FakeClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.messages = _FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-runtime-settings-value")
    monkeypatch.setenv("CLAUDE_MODEL", "runtime-model")
    monkeypatch.setattr(research_loop_module.anthropic, "Anthropic", _FakeClient)

    brief = research_loop_module.run_research_loop_sync(
        "Propellerhead Limited",
        "Auckland, New Zealand",
        "Digital services",
    )

    assert brief.risk_free_rate == 4.65
    assert captured == {
        "api_key": "sk-ant-runtime-settings-value",
        "model": "runtime-model",
    }


def test_research_loop_includes_management_supplied_public_source_hints(monkeypatch):
    """Management-supplied URLs should guide web research without becoming required questions."""
    captured = {}
    valid_json = __import__("json").dumps(_valid_brief_kwargs())

    class _FakeMessages:
        def create(self, **kwargs):
            captured["prompt"] = kwargs["messages"][0]["content"]
            return SimpleNamespace(
                content=[_StubTextBlock(valid_json)],
                stop_reason="end_turn",
                usage=SimpleNamespace(
                    server_tool_use={},
                    input_tokens=100,
                    output_tokens=200,
                ),
            )

    class _FakeClient:
        def __init__(self, api_key):
            self.messages = _FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-runtime-settings-value")
    monkeypatch.setattr(research_loop_module.anthropic, "Anthropic", _FakeClient)

    research_loop_module.run_research_loop_sync(
        "Source Hints Limited",
        "Auckland, New Zealand",
        "Professional services",
        company_website="https://source-hints.example",
        public_source_urls=[
            "https://companies-register.companiesoffice.govt.nz/source-hints",
            "https://www.linkedin.com/company/source-hints",
        ],
    )

    assert "Official website supplied by management: https://source-hints.example" in captured["prompt"]
    assert "Additional public source URLs supplied by management:" in captured["prompt"]
    assert "Location: Auckland, New Zealand" in captured["prompt"]
    assert "companies-register.companiesoffice.govt.nz/source-hints" in captured["prompt"]
    assert "linkedin.com/company/source-hints" in captured["prompt"]
    assert "Use the management-supplied website and source URLs first" in captured["prompt"]
    assert "Treat supplied URLs as source hints" in captured["prompt"]
    assert "Do not use a public fact in the brief unless the supporting source URL is retained in sources" in captured["prompt"]
    assert "If a supplied link cannot be corroborated, mention only that it was supplied as a matching hint" in captured["prompt"]


def test_research_loop_rejects_malformed_management_source_hints_before_provider_call(monkeypatch):
    """Direct research-loop calls should receive already-normalised public URLs."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-runtime-settings-value")

    with pytest.raises(ValueError, match="company website must be a full public HTTP\\(S\\) URL"):
        research_loop_module.run_research_loop_sync(
            "Source Hints Limited",
            "Auckland, New Zealand",
            "Professional services",
            company_website="source-hints.example",
        )

    with pytest.raises(ValueError, match="public source URL 1 must be a full public HTTP\\(S\\) URL"):
        research_loop_module.run_research_loop_sync(
            "Source Hints Limited",
            "Auckland, New Zealand",
            "Professional services",
            public_source_urls=["linkedin.com/company/source-hints"],
        )


def test_research_loop_rejects_private_management_source_hints_before_provider_call(monkeypatch):
    """Source hints are public online avenues, not local or private-network locations."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-runtime-settings-value")

    with pytest.raises(ValueError, match="company website must be a public HTTP\\(S\\) URL"):
        research_loop_module.run_research_loop_sync(
            "Source Hints Limited",
            "Auckland, New Zealand",
            "Professional services",
            company_website="http://localhost:3000/profile",
        )

    with pytest.raises(ValueError, match="public source URL 1 must be a public HTTP\\(S\\) URL"):
        research_loop_module.run_research_loop_sync(
            "Source Hints Limited",
            "Auckland, New Zealand",
            "Professional services",
            public_source_urls=["http://192.168.1.10/internal-source"],
        )
